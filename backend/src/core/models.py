from pydantic import BaseModel


class AuthRequest(BaseModel):
    email: str
    password: str


class TestRequest(BaseModel):
    target_url: str
    prompt: str
    user_id: str | None = None


class TestRunResult(BaseModel):
    execution_id: str
    status: str
    result: str | None
    report_url: str | None
    test_plan: str | None = None
    script_code: str | None = None

class PlanRequest(BaseModel):
    target_url: str
    prompt: str

class ScriptRequest(BaseModel):
    target_url: str
    test_plan: str

class ExecuteScriptRequest(BaseModel):
    target_url: str
    prompt: str
    user_id: str | None = None
    script_code: str
    test_plan: str | None = None
