from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable


@dataclass
class AgentResult:
    messages: list[dict[str, Any]]
    metadata: dict[str, Any] = field(default_factory=dict)
    success: bool = True
    error: str | None = None


@runtime_checkable
class LLMClient(Protocol):
    async def chat(self, messages: list[dict[str, str]]) -> str: ...


class BridgeAdapter(ABC):
    @abstractmethod
    async def connect(self, config: dict[str, Any]) -> None: ...
    @abstractmethod
    async def disconnect(self) -> None: ...
    @abstractmethod
    async def health_check(self) -> bool: ...
    @abstractmethod
    async def send_test(self, test_data: dict[str, Any]) -> AgentResult: ...
    async def get_judge_llm(self) -> LLMClient | None:
        return None
    @abstractmethod
    def adapter_type(self) -> str: ...
    @abstractmethod
    def target_description(self) -> str: ...
