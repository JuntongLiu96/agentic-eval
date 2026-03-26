from app.bridge.base import BridgeAdapter
from app.bridge.http_adapter import HTTPAdapter
from app.bridge.python_adapter import PythonAdapter
from app.bridge.stdio_adapter import StdioAdapter

ADAPTER_TYPES: dict[str, type[BridgeAdapter]] = {
    "http": HTTPAdapter, "python": PythonAdapter, "stdio": StdioAdapter,
}

def create_adapter(adapter_type: str) -> BridgeAdapter:
    cls = ADAPTER_TYPES.get(adapter_type)
    if cls is None:
        raise ValueError(f"Unknown adapter type: {adapter_type}. Available: {list(ADAPTER_TYPES.keys())}")
    return cls()
