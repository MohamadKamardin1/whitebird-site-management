import pytest
from constance import config


@pytest.mark.django_db
def test_system_admin_can_save_integration_settings_without_secret_echo(admin_client):
    previous_deepseek = config.DEEPSEEK_API_KEY
    previous_mapbox = config.MAPBOX_PUBLIC_TOKEN
    try:
        response = admin_client.patch(
            "/api/site-management/v1/integrations/settings",
            data={
                "deepseek_api_key": "sk-test-integration-key",
                "mapbox_public_token": "pk.test-mapbox-token",
            },
            content_type="application/json",
        )
        assert response.status_code == 200
        body = response.json()
        assert body["deepseek_configured"] is True
        assert body["deepseek_key_suffix"] == "-key"
        assert body["mapbox_public_token"] == "pk.test-mapbox-token"
        assert "sk-test-integration-key" not in response.content.decode()

        read_response = admin_client.get("/api/site-management/v1/integrations/settings")
        assert read_response.status_code == 200
        assert read_response.json()["deepseek_key_suffix"] == "-key"
    finally:
        config.DEEPSEEK_API_KEY = previous_deepseek
        config.MAPBOX_PUBLIC_TOKEN = previous_mapbox


@pytest.mark.django_db
def test_non_admin_cannot_update_integration_settings(site_supervisor_client):
    response = site_supervisor_client.patch(
        "/api/site-management/v1/integrations/settings",
        data={"mapbox_public_token": "pk.not-authorized"},
        content_type="application/json",
    )
    assert response.status_code in {401, 403}
