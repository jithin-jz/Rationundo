from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_404_html_page():
    response = client.get("/nonexistent-page-path")
    assert response.status_code == 404
    assert "text/html" in response.headers["content-type"]
    assert "പേജ് കണ്ടെത്തിയില്ല" in response.text
    assert "404 Error" in response.text


def test_404_api_json():
    response = client.get("/api/nonexistent")
    assert response.status_code == 404
    assert "application/json" in response.headers["content-type"]
    assert response.json() == {"detail": "Not Found"}
