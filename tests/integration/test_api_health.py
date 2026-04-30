"""冒烟测试：FastAPI /health 端点不依赖完整生命周期。"""

from __future__ import annotations

import pytest


@pytest.fixture(scope="module")
def client():
    """导入 app 前先 patch lifespan，避免真实 DB/Redis 连接。"""
    import sys
    from contextlib import asynccontextmanager
    from unittest.mock import MagicMock, patch

    @asynccontextmanager
    async def _fake_lifespan(app):
        app.state.services = {}
        # /health 端点访问 app.state.conn_mgr.connected，需要提供 mock
        conn_mgr = MagicMock()
        conn_mgr.connected = False
        app.state.conn_mgr = conn_mgr
        yield

    # 同时 patch 两处：
    #   1. src.core.lifespan.lifespan —— reload 时 from src.core.lifespan import lifespan 会读这里
    #   2. src.core.main.lifespan     —— 若模块已缓存，main.py 内的绑定也需要替换
    with (
        patch("src.core.lifespan.lifespan", new=_fake_lifespan),
        patch("src.core.main.lifespan", new=_fake_lifespan),
    ):
        # 移除已缓存的 main 模块，确保重新 import 时能读到 patched lifespan
        sys.modules.pop("src.core.main", None)

        from fastapi.testclient import TestClient

        import src.core.main as main_mod  # noqa: PLC0415

        with TestClient(main_mod.app, raise_server_exceptions=False) as c:
            yield c


class TestHealthEndpoint:
    def test_health_returns_200(self, client):
        """smoke test：/health 端点无需完整生命周期即可响应 200。"""
        response = client.get("/health")
        assert response.status_code == 200

    def test_health_response_structure(self, client):
        """响应 body 包含 status 字段，healthy 时值为 'healthy'。"""
        response = client.get("/health")
        data = response.json()
        assert data["status"] == "healthy"
        assert "ws_connected" in data
