from app.services.local_model import LocalModelClient


def test_local_model_defaults_to_deterministic(monkeypatch) -> None:
    monkeypatch.delenv("LOCAL_MODEL_PROVIDER", raising=False)

    status = LocalModelClient().status()

    assert status.enabled is False
    assert status.provider == "deterministic"
    assert status.available is True


def test_local_model_refuses_non_local_endpoint(monkeypatch) -> None:
    monkeypatch.setenv("LOCAL_MODEL_PROVIDER", "ollama")
    monkeypatch.setenv("LOCAL_MODEL_ENDPOINT", "https://example.com")

    status = LocalModelClient().status()

    assert status.enabled is True
    assert status.available is False
    assert "Refusing non-local model endpoint" in status.message
