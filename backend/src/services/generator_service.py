import asyncio
from src.agent.factory import build_llm
from src.core.models import PlanRequest, ScriptRequest

class GeneratorService:
    def __init__(self):
        # We use a more capable model for script generation, and instant for planning
        self.planner_llm = build_llm(model="llama-3.3-70b-versatile", temperature=0.1)
        self.coder_llm = build_llm(model="llama-3.3-70b-versatile", temperature=0.1)

    async def generate_plan(self, request: PlanRequest) -> str:
        prompt = (
            f"You are a Senior QA Automation Engineer.\n"
            f"Target URL: {request.target_url}\n"
            f"User Objective: {request.prompt}\n\n"
            "Create a concise, step-by-step test plan for this objective. "
            "List exactly what elements need to be interacted with and what assertions should be made. "
            "Do not write code, just the plan."
        )
        response = await self.planner_llm.ainvoke([("human", prompt)])
        return response.content

    async def generate_script(self, request: ScriptRequest) -> str:
        prompt = (
            "You are an expert Python Playwright SDET.\n"
            "Generate a complete, runnable asynchronous Python Playwright script based on the following test plan.\n"
            f"Target URL: {request.target_url}\n\n"
            f"Test Plan:\n{request.test_plan}\n\n"
            "Requirements:\n"
            "1. Use `asyncio` and `async_playwright`.\n"
            "2. Ensure robust waiting and error handling (try/except blocks).\n"
            "3. Add informative print statements for each step so it acts as an execution log.\n"
            "4. At the end, take a screenshot and save it to `evidence.png`.\n"
            "5. The code should be fully self-contained in a single file and executable via `python script.py`.\n"
            "Output ONLY the python code inside ```python ``` blocks, no other text."
        )
        response = await self.coder_llm.ainvoke([("human", prompt)])
        
        # Clean up the output to extract just the code
        content = response.content
        if "```python" in content:
            content = content.split("```python")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()
            
        return content
