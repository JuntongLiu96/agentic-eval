import importlib
from typing import Any
from app.bridge.base import AgentResult, BridgeAdapter, LLMClient

class PythonAdapter(BridgeAdapter):
    def __init__(self):
        self._instance: Any = None
        self._module_path: str = ""
        self._class_name: str = ""
        self._description: str = ""

    async def connect(self, config: dict[str, Any]) -> None:
        self._module_path = config["module"]
        self._class_name = config["class"]
        self._description = config.get("description", f"Python agent: {self._module_path}.{self._class_name}")
        module = importlib.import_module(self._module_path)
        cls = getattr(module, self._class_name)
        self._instance = cls()
        if hasattr(self._instance, "connect"):
            await self._instance.connect(config)

    async def disconnect(self) -> None:
        if self._instance and hasattr(self._instance, "disconnect"):
            await self._instance.disconnect()
        self._instance = None

    async def health_check(self) -> bool:
        if not self._instance: return False
        if hasattr(self._instance, "health_check"):
            return await self._instance.health_check()
        return True

    async def send_test(self, test_data: dict[str, Any]) -> AgentResult:
        if not self._instance:
            return AgentResult(messages=[], success=False, error="Not connected")
        try:
            result = await self._instance.send_test(test_data)
            if isinstance(result, AgentResult): return result
            return AgentResult(
                messages=result.get("messages", []),
                sub_agent_messages=result.get("sub_agent_messages", []),
                metadata=result.get("metadata", {}),
                success=result.get("success", True),
                error=result.get("error"),
            )
        except Exception as e:
            return AgentResult(messages=[], success=False, error=str(e))

    async def get_judge_llm(self) -> LLMClient | None:
        if self._instance and hasattr(self._instance, "get_judge_llm"):
            return await self._instance.get_judge_llm()
        return None

    def adapter_type(self) -> str: return "python"
    def target_description(self) -> str: return self._description
