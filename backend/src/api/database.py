import os
from passlib.context import CryptContext
from datetime import datetime, timezone
from pymongo import MongoClient

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
client = None
mongo_available = True

# In-memory fallbacks when MongoDB is offline
_in_memory_users = {}
_in_memory_test_runs = []
_in_memory_selector_cache = {}  # (url_path, element_description) -> dict

def get_db():
    global client, mongo_available
    if not mongo_available:
        return None
    if client is None:
        try:
            # Short 2-second timeout to avoid hanging if DB is not running
            client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=2000)
            client.admin.command('ping')
            db = client.get_database("ai_qa_db")
            # Create indexes for performance
            db.test_runs.create_index([("user_id", 1), ("created_at", -1)])
            db.users.create_index("email", unique=True)
            db.selector_memory.create_index([("url_path", 1), ("element_description", 1)])
            print("[DB] Connected to MongoDB successfully.")
        except Exception as e:
            print(f"[DB] [WARNING] MongoDB connection failed ({e}). Falling back to in-memory database.")
            mongo_available = False
            return None
    try:
        return client.get_database("ai_qa_db")
    except Exception:
        mongo_available = False
        return None

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

class DatabaseManager:
    @staticmethod
    def hash_password(password: str) -> str:
        return pwd_context.hash(password)

    @staticmethod
    def create_user(email: str, password: str) -> bool:
        db = get_db()
        if db is not None:
            try:
                if db.users.find_one({"email": email}):
                    return False
                db.users.insert_one({
                    "email": email, 
                    "password": DatabaseManager.hash_password(password)
                })
                return True
            except Exception as e:
                print(f"DB Error creating user: {e}")
                return False
        else:
            if email in _in_memory_users:
                return False
            _in_memory_users[email] = DatabaseManager.hash_password(password)
            return True

    @staticmethod
    def verify_user(email: str, password: str) -> bool:
        db = get_db()
        if db is not None:
            try:
                user = db.users.find_one({"email": email})
                if user and pwd_context.verify(password, user["password"]):
                    return True
                return False
            except Exception as e:
                print(f"DB Error verifying user: {e}")
                return False
        else:
            hashed = _in_memory_users.get(email)
            if hashed and pwd_context.verify(password, hashed):
                return True
            return False

    @staticmethod
    def save_test_run(
        user_id: str,
        execution_id: str,
        target_url: str,
        prompt: str,
        status: str,
        pdf_path: str,
        report_url: str | None = None,
        result: str | None = None,
        test_plan: str | None = None,
        script_code: str | None = None,
        execution_time: float = 0.0,
        llm_calls: int = 0,
        cache_hits: int = 0,
        cache_misses: int = 0,
        generated_scenarios: int = 0,
        assertions_passed: int = 0,
        export_success: bool = False
    ):
        db = get_db()
        test_data = {
            "user_id": user_id,
            "execution_id": execution_id,
            "target_url": target_url,
            "prompt": prompt,
            "status": status,
            "pdf_path": pdf_path,
            "report_url": report_url,
            "result": result,
            "test_plan": test_plan,
            "script_code": script_code,
            "execution_time": execution_time,
            "llm_calls": llm_calls,
            "cache_hits": cache_hits,
            "cache_misses": cache_misses,
            "generated_scenarios": generated_scenarios,
            "assertions_passed": assertions_passed,
            "export_success": export_success,
            "created_at": datetime.now(timezone.utc)
        }
        if db is not None:
            try:
                inserted = db.test_runs.insert_one(test_data)
                return str(inserted.inserted_id)
            except Exception as e:
                print(f"DB Error saving test run: {e}")
                # Fall back to in-memory anyway
        
        # In-memory storage fallback
        _in_memory_test_runs.append(test_data)
        return "in_memory_id_" + execution_id

    @staticmethod
    def get_history(user_id: str):
        db = get_db()
        if db is not None:
            try:
                runs = db.test_runs.find({"user_id": user_id}).sort("created_at", -1)
                history = []
                for run in runs:
                    run["_id"] = str(run["_id"])
                    created_at = run.get("created_at")
                    if created_at:
                        run["created_at"] = created_at.isoformat()
                    history.append(run)
                return history
            except Exception as e:
                print(f"DB Error loading history: {e}")
        
        # In-memory history fallback
        user_runs = [r for r in _in_memory_test_runs if r["user_id"] == user_id]
        sorted_runs = sorted(user_runs, key=lambda x: x["created_at"], reverse=True)
        result = []
        for r in sorted_runs:
            item = r.copy()
            item["_id"] = "in_memory_" + item["execution_id"]
            if isinstance(item["created_at"], datetime):
                item["created_at"] = item["created_at"].isoformat()
            result.append(item)
        return result

    @staticmethod
    def get_cached_selectors(url_path: str, element_description: str) -> list[dict]:
        db = get_db()
        results = []
        if db is not None:
            try:
                records = db.selector_memory.find({
                    "url_path": url_path,
                    "element_description": element_description
                })
                for r in records:
                    r["_id"] = str(r["_id"])
                    results.append(r)
                return results
            except Exception as e:
                print(f"DB Error fetching cached selectors: {e}")
        
        # In-memory lookup fallback
        for key, record in _in_memory_selector_cache.items():
            # key: (url_path, element_description, parent_anchor)
            if key[0] == url_path and key[1] == element_description:
                results.append(record)
        return results

    @staticmethod
    def save_selector_memory(url_path: str, element_description: str, parent_anchor: str, resolved_selector: str, success: bool):
        db = get_db()
        confidence_score = 1.0
        
        # 1. Query current record if exists to get current confidence score
        current_record = None
        if db is not None:
            try:
                current_record = db.selector_memory.find_one({
                    "url_path": url_path,
                    "element_description": element_description,
                    "parent_anchor": parent_anchor
                })
            except Exception as e:
                print(f"DB Error finding record: {e}")
        else:
            current_record = _in_memory_selector_cache.get((url_path, element_description, parent_anchor))

        if current_record:
            confidence_score = current_record.get("confidence_score", 1.0)
            
        # 2. Adjust weight W
        if success:
            confidence_score = min(1.0, confidence_score + 0.2)
        else:
            confidence_score = confidence_score * 0.5
            
        # 3. Evict if W < 0.3
        evict = confidence_score < 0.3
        
        if db is not None:
            try:
                query = {
                    "url_path": url_path,
                    "element_description": element_description,
                    "parent_anchor": parent_anchor
                }
                if evict:
                    db.selector_memory.delete_one(query)
                    print(f"[DEEM Cache] Evicted stale database selector for '{element_description}' (W={confidence_score:.2f})")
                else:
                    update = {
                        "$set": {
                            "resolved_selector": resolved_selector,
                            "confidence_score": confidence_score,
                            "last_used": datetime.now(timezone.utc)
                        },
                        "$inc": {
                            "success_count": 1 if success else 0,
                            "fail_count": 0 if success else 1
                        }
                    }
                    db.selector_memory.update_one(query, update, upsert=True)
                return True
            except Exception as e:
                print(f"DB Error saving selector memory: {e}")
        
        # In-memory storage / eviction fallback
        key = (url_path, element_description, parent_anchor)
        if evict:
            if key in _in_memory_selector_cache:
                del _in_memory_selector_cache[key]
                print(f"[DEEM Cache] Evicted stale in-memory selector for '{element_description}' (W={confidence_score:.2f})")
        else:
            record = _in_memory_selector_cache.get(key)
            if not record:
                record = {
                    "url_path": url_path,
                    "element_description": element_description,
                    "parent_anchor": parent_anchor,
                    "resolved_selector": resolved_selector,
                    "confidence_score": confidence_score,
                    "success_count": 0,
                    "fail_count": 0,
                    "last_used": datetime.now(timezone.utc)
                }
            record["resolved_selector"] = resolved_selector
            record["confidence_score"] = confidence_score
            record["last_used"] = datetime.now(timezone.utc)
            if success:
                record["success_count"] += 1
            else:
                record["fail_count"] += 1
            _in_memory_selector_cache[key] = record
        return True
