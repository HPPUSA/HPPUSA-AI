import logging

import App


class _FakeMessage:
    content = "A safe, mocked HPPUSA response."


class _FakeChoice:
    message = _FakeMessage()


class _FakeCompletion:
    choices = [_FakeChoice()]


class _FakeCompletions:
    def create(self, **kwargs):
        self.kwargs = kwargs
        return _FakeCompletion()


class _FakeChat:
    def __init__(self):
        self.completions = _FakeCompletions()


class _FakeGroq:
    last_instance = None

    def __init__(self, api_key, **kwargs):
        self.api_key = api_key
        self.timeout = kwargs.get("timeout")
        self.max_retries = kwargs.get("max_retries")
        self.chat = _FakeChat()
        _FakeGroq.last_instance = self


def setup_function():
    App._request_history.clear()


def test_homepage_returns_200():
    response = App.app.test_client().get("/")
    assert response.status_code == 200
    assert b"HPPUSA AI" in response.data


def test_valid_chat_uses_mocked_provider(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "test-key-not-real")
    monkeypatch.setattr(App, "Groq", _FakeGroq)

    response = App.app.test_client().post(
        "/chat", json={"message": "Help me make a maintenance checklist"}
    )

    assert response.status_code == 200
    assert response.get_json()["reply"] == "A safe, mocked HPPUSA response."
    assert _FakeGroq.last_instance.timeout == 25.0
    assert _FakeGroq.last_instance.max_retries == 0
    sent_messages = _FakeGroq.last_instance.chat.completions.kwargs["messages"]
    assert "WATER NEAR ELECTRICITY — STRICT SAFETY OVERRIDE" in sent_messages[0]["content"]


def test_blank_message_returns_400():
    response = App.app.test_client().post("/chat", json={"message": "   "})
    assert response.status_code == 400


def test_message_over_3000_characters_returns_400():
    response = App.app.test_client().post("/chat", json={"message": "x" * 3001})
    assert response.status_code == 400


def test_oversized_request_body_returns_413():
    response = App.app.test_client().post(
        "/chat",
        data=b"x" * (16 * 1024 + 1),
        content_type="application/json",
    )
    assert response.status_code == 413
    assert "error" in response.get_json()


def test_rate_limit_returns_429_after_ten_requests(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    client = App.app.test_client()
    responses = [
        client.post("/chat", json={"message": "hello"}, environ_base={"REMOTE_ADDR": "192.0.2.10"})
        for _ in range(11)
    ]
    assert all(response.status_code == 500 for response in responses[:10])
    assert responses[10].status_code == 429
    assert responses[10].headers["Retry-After"] == "60"


def test_missing_api_key_returns_safe_error(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    response = App.app.test_client().post("/chat", json={"message": "hello"})
    assert response.status_code == 500
    assert "not connected" in response.get_json()["error"].lower()
    assert "GROQ_API_KEY" not in response.get_data(as_text=True)


def test_provider_failure_does_not_expose_exception_or_prompt(monkeypatch, caplog):
    class _ExplodingGroq:
        def __init__(self, api_key, **kwargs):
            self.chat = self

        @property
        def completions(self):
            return self

        def create(self, **kwargs):
            raise RuntimeError("provider-secret-detail")

    monkeypatch.setenv("GROQ_API_KEY", "test-key-not-real")
    monkeypatch.setattr(App, "Groq", _ExplodingGroq)
    caplog.set_level(logging.ERROR)

    response = App.app.test_client().post(
        "/chat", json={"message": "private-customer-prompt"}
    )

    assert response.status_code == 500
    body = response.get_data(as_text=True)
    assert "provider-secret-detail" not in body
    assert "private-customer-prompt" not in body
    assert "test-key-not-real" not in body
    assert response.get_json()["request_id"]
    assert "provider-secret-detail" not in caplog.text
    assert "private-customer-prompt" not in caplog.text


def test_rate_limit_cannot_be_bypassed_with_forwarded_headers(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    client = App.app.test_client()
    for index in range(10):
        response = client.post(
            "/chat",
            json={"message": "hello"},
            headers={"X-Forwarded-For": f"198.51.100.{index + 1}"},
            environ_base={"REMOTE_ADDR": "192.0.2.25"},
        )
        assert response.status_code == 500

    blocked = client.post(
        "/chat",
        json={"message": "hello"},
        headers={"X-Forwarded-For": "203.0.113.77"},
        environ_base={"REMOTE_ADDR": "192.0.2.25"},
    )
    assert blocked.status_code == 429
