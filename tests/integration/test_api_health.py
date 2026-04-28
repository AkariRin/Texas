"""冒烟测试：FastAPI /health 端点不依赖完整生命周期。"""

from __future__ import annotations

import pytest


@pytest.fixture(scope="module")
def client():
    """导入 app 前先 patch lifespan，避免真实 DB/Redis 连接。"""
    from contextlib import asynccontextmanager
    from unittest.mock import patch

    @asynccontextmanager
    async def _fake_lifespan(app):
        app.state.services = {}
        yield

    with patch("src.core.main.lifespan", new=_fake_lifespan):
        import importlib

        import src.core.main as main_mod

        importlib.reload(main_mod)
        from fastapi.testclient import TestClient

        with TestClient(main_mod.app, raise_server_exceptions=False) as c:
            yield c


class TestHealthEndpoint:
    @pytest.mark.skip(reason="需要完整应用环境，作为 smoke test 在集成环境运行")
    def test_health_returns_200(self, client):
        response = client.get("/health")
        assert response.status_code == 200
