import pytest
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.config.settings import settings
import json
import os

client = TestClient(app)

def test_settings_workflow():
    # 1. Test unlock with invalid PIN
    response = client.post("/api/v1/settings/unlock", json={"pin": "wrong_pin"})
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid settings PIN."

    # 2. Test unlock with valid PIN
    valid_pin = settings.SETTINGS_PIN
    response = client.post("/api/v1/settings/unlock", json={"pin": valid_pin})
    assert response.status_code == 200
    token = response.json().get("token")
    assert token is not None

    # 3. Test get config without token
    response = client.get("/api/v1/settings/fyers-config")
    assert response.status_code == 401

    # 4. Test get config with invalid token
    response = client.get(
        "/api/v1/settings/fyers-config",
        headers={"Authorization": "Bearer invalidtoken"}
    )
    assert response.status_code == 401

    # 5. Test get config with valid token
    response = client.get(
        "/api/v1/settings/fyers-config",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "app_id_masked" in data
    assert "redirect_uri" in data
    assert "authenticated" in data

    # Backup existing config if any
    config_existed = settings.config_path.exists()
    old_content = None
    if config_existed:
        old_content = settings.config_path.read_text()

    try:
        # 6. Test update config with valid token
        new_config = {
            "app_id": "TEST_APP_ID_LONG_ENOUGH_FOR_MASKING",
            "secret_id": "TEST_SECRET_ID",
            "redirect_uri": "http://localhost/callback"
        }
        response = client.post(
            "/api/v1/settings/fyers-config",
            json=new_config,
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200
        assert response.json()["status"] == "success"

        # Verify that settings dynamically updated
        assert settings.FYERS_APP_ID == "TEST_APP_ID_LONG_ENOUGH_FOR_MASKING"
        assert settings.FYERS_SECRET_ID == "TEST_SECRET_ID"
        assert settings.FYERS_REDIRECT_URI == "http://localhost/callback"

        # Test login-url endpoint
        response = client.get(
            "/api/v1/settings/login-url",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200
        assert "login_url" in response.json()
        assert "TEST_APP_ID_LONG_ENOUGH" in response.json()["login_url"]
    finally:
        # Restore old config
        if config_existed:
            settings.config_path.write_text(old_content)
        elif settings.config_path.exists():
            settings.config_path.unlink()

def test_settings_rate_limiting():
    client_ip = "testclient"
    
    # Reset failures before test starts
    from backend.app.api.v1.settings import clear_failed_attempts, _local_attempts
    _local_attempts.clear()
    clear_failed_attempts(client_ip)
    clear_failed_attempts("127.0.0.1")

    # Attempt 5 failures
    for _ in range(5):
        response = client.post("/api/v1/settings/unlock", json={"pin": "wrong"})
        assert response.status_code in [401, 429]
        
    # The 6th attempt should definitely lock out with 429
    response = client.post("/api/v1/settings/unlock", json={"pin": settings.SETTINGS_PIN})
    assert response.status_code == 429
    assert response.json()["detail"] == "Too many failed attempts. Try again later."
    
    # Reset/clear attempts
    _local_attempts.clear()
    clear_failed_attempts(client_ip)
    clear_failed_attempts("127.0.0.1")
    
    # Now it should succeed
    response = client.post("/api/v1/settings/unlock", json={"pin": settings.SETTINGS_PIN})
    assert response.status_code == 200
