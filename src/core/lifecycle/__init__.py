"""服务生命周期管理 —— @startup / @shutdown 装饰器声明式生命周期。"""

from src.core.lifecycle.registry import shutdown, startup

__all__ = ["shutdown", "startup"]
