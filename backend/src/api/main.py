from fastapi import FastAPI, HTTPException, Query, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
import os

from src.core.config import AUTH_BYPASS, DEFAULT_USER_ID, REPORT_DIR
from src.core.models import AuthRequest, TestRequest, PlanRequest, ScriptRequest, ExecuteScriptRequest
from src.services.auth_service import AuthService
from src.services.run_service import RunService
from src.services.generator_service import GeneratorService
from src.api.auth_bearer import JWTBearer, create_access_token

app = FastAPI()
auth_service = AuthService()
run_service = RunService()
generator_service = GeneratorService()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

os.makedirs(REPORT_DIR, exist_ok=True)
app.mount("/report", StaticFiles(directory=REPORT_DIR), name="report")

@app.post("/api/v1/login")
async def login(data: AuthRequest):
    if not AUTH_BYPASS and not auth_service.login(data.email, data.password):
        raise HTTPException(status_code=401, detail="Invalid email or password.")
    token = create_access_token(data.email)
    return {"status": "success", "user_id": data.email, "token": token}

@app.post("/api/v1/signup")
async def signup(data: AuthRequest):
    if not auth_service.signup(data.email, data.password):
        raise HTTPException(status_code=409, detail="User already exists or signup failed.")
    token = create_access_token(data.email)
    return {"status": "success", "user_id": data.email, "token": token}

@app.get("/api/v1/history")
async def get_history(user_id: str = Depends(JWTBearer())):
    return run_service.list_history(user_id)

@app.post("/api/v1/generate-plan")
async def generate_plan(request: PlanRequest, user_id: str = Depends(JWTBearer())):
    plan = await generator_service.generate_plan(request)
    return {"status": "success", "test_plan": plan}

@app.post("/api/v1/generate-script")
async def generate_script(request: ScriptRequest, user_id: str = Depends(JWTBearer())):
    script = await generator_service.generate_script(request)
    return {"status": "success", "script": script}

@app.post("/api/v1/execute")
async def execute_test(request: TestRequest, user_id: str = Depends(JWTBearer())):
    return await run_service.execute_test(request, user_id)

@app.post("/api/v1/execute/stream")
async def execute_test_stream(request: TestRequest, user_id: str = Depends(JWTBearer())):
    return StreamingResponse(
        run_service.stream_execute_test(request, user_id),
        media_type="text/event-stream",
    )

@app.post("/api/v1/execute-script/stream")
async def execute_generated_script_stream(request: ExecuteScriptRequest, user_id: str = Depends(JWTBearer())):
    return StreamingResponse(
        run_service.stream_execute_script(request, user_id),
        media_type="text/event-stream",
    )

@app.post("/api/v1/execute/{execution_id}/resume")
async def resume_execution(execution_id: str):
    from src.agent.browser import resume_paused_execution
    success = resume_paused_execution(execution_id)
    if not success:
        raise HTTPException(status_code=404, detail="No active pause found for this execution ID.")
    return {"status": "success", "message": "Execution resumed."}
