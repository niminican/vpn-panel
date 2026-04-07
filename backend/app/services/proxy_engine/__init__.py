from app.services.proxy_engine.base import ProxyEngine
from app.services.proxy_engine.xray import XrayEngine
from app.services.proxy_engine.singbox import SingboxEngine


def get_engine(engine_type: str) -> ProxyEngine:
    """Factory: get the right engine by name."""
    engines = {
        "xray": XrayEngine,
        "singbox": SingboxEngine,
    }
    cls = engines.get(engine_type)
    if not cls:
        raise ValueError(f"Unknown engine: {engine_type}. Available: {list(engines.keys())}")
    return cls()
