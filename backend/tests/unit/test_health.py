def test_health(client) -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_root(client) -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["status"] == "running"
