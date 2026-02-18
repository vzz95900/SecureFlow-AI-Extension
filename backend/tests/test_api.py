"""
Tests for the FastAPI endpoints (sanitize, restore, health).
"""
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.asyncio
async def test_health_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "version" in data


@pytest.mark.asyncio
async def test_root_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/")
        assert response.status_code == 200


@pytest.mark.asyncio
async def test_sanitize_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/api/v1/sanitize", json={
            "text": "My name is John Doe and my SSN is 123-45-6789",
            "sensitivity": "high",
        })
        assert response.status_code == 200
        data = response.json()
        assert "sanitized_text" in data
        assert "session_id" in data
        assert data["entities_found"] >= 0


@pytest.mark.asyncio
async def test_sanitize_then_restore():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Sanitize
        san_response = await client.post("/api/v1/sanitize", json={
            "text": "Contact Alice at alice@example.com",
            "sensitivity": "high",
        })
        assert san_response.status_code == 200
        san_data = san_response.json()
        session_id = san_data["session_id"]

        # Restore
        res_response = await client.post("/api/v1/restore", json={
            "text": san_data["sanitized_text"],
            "session_id": session_id,
        })
        assert res_response.status_code == 200
        res_data = res_response.json()
        assert "restored_text" in res_data


@pytest.mark.asyncio
async def test_sanitize_empty_text_rejected():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/api/v1/sanitize", json={
            "text": "",
            "sensitivity": "high",
        })
        assert response.status_code == 422  # Validation error
