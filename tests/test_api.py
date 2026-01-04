from fastapi.testclient import TestClient
from ai_project.app import app


client = TestClient(app)


def test_root():
    r = client.get("/")
    assert r.status_code == 200
    assert r.json().get("status") == "ok"


def test_greet_api():
    r = client.get("/greet/Alice")
    assert r.status_code == 200
    assert r.json() == {"message": "Hello, Alice!"}
