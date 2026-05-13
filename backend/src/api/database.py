import os
from passlib.context import CryptContext
from datetime import datetime, timezone
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
client = None

def get_db():
    global client
    if client is None:
        try:
            client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
            client.admin.command('ping')
            print("🔌 Connecting to MongoDB...")
        except ConnectionFailure as e:
            print(f"DB Error: {e}")
            raise e
    return client.get_database("ai_qa_db")

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

class DatabaseManager:
    @staticmethod
    def hash_password(password: str) -> str:
        return pwd_context.hash(password)

    @staticmethod
    def create_user(email: str, password: str) -> bool:
        try:
            db = get_db()
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

    @staticmethod
    def verify_user(email: str, password: str) -> bool:
        try:
            db = get_db()
            user = db.users.find_one({"email": email})
            if user and pwd_context.verify(password, user["password"]):
                return True
            return False
        except Exception as e:
            print(f"DB Error verifying user: {e}")
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
    ):
        try:
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
                "created_at": datetime.now(timezone.utc)
            }
            result = db.test_runs.insert_one(test_data)
            return str(result.inserted_id)
        except Exception as e:
            raise e

    @staticmethod
    def get_history(user_id: str):
        try:
            db = get_db()
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
            return []
