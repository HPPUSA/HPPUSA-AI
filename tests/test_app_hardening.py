import logging
from concurrent.futures import ThreadPoolExecutor

from flask.testing import FlaskClient

import App


class _CloudflareTestClient(FlaskClient):
    """Model the normal edge header for ordinary local endpoint tests."""

    def post(self, *args, **kwargs):
        headers = dict(kwargs.pop("headers", {}) or {})
        omit_cf_header = headers.pop("TEST-OMIT-CF-HEADER", False)
        if not omit_cf_header:
            headers.setdefault("CF-Connecting-IP", "192.0.2.200")
        kwargs["headers"] = headers
        return super().post(*args, **kwargs)


App.app.test_client_class = _CloudflareTestClient


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


def test_frontend_security_libraries_are_version_pinned():
    response = App.app.test_client().get("/")
    html = response.get_data(as_text=True)

    assert "marked@18.1.3/lib/marked.umd.js" in html
    assert "dompurify@3.4.17/dist/purify.min.js" in html
    assert "marked.min.js" not in html
    assert "dompurify@3.2.6" not in html


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


def test_non_object_json_payload_returns_400():
    client = App.app.test_client()
    for payload in (["unexpected"], "unexpected", 7, True):
        response = client.post("/chat", json=payload)
        assert response.status_code == 400
        assert "JSON object" in response.get_json()["error"]


def test_non_string_message_returns_400():
    client = App.app.test_client()
    for value in (123, ["text"], {"text": "value"}):
        response = client.post("/chat", json={"message": value})
        assert response.status_code == 400
        assert response.get_json()["error"] == "Please enter a question."


def test_malformed_json_returns_400():
    response = App.app.test_client().post(
        "/chat", data="{not-json", content_type="application/json"
    )
    assert response.status_code == 400
    assert "JSON object" in response.get_json()["error"]


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


def test_rate_limit_uses_cloudflare_client_ip_not_forwarded_for(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    client = App.app.test_client()
    for index in range(10):
        response = client.post(
            "/chat",
            json={"message": "hello"},
            headers={
                "CF-Connecting-IP": "192.0.2.25",
                "X-Forwarded-For": f"198.51.100.{index + 1}",
            },
            environ_base={"REMOTE_ADDR": "10.0.0.1"},
        )
        assert response.status_code == 500

    blocked = client.post(
        "/chat",
        json={"message": "hello"},
        headers={
            "CF-Connecting-IP": "192.0.2.25",
            "X-Forwarded-For": "203.0.113.77",
        },
        environ_base={"REMOTE_ADDR": "10.0.0.1"},
    )
    assert blocked.status_code == 429

    separate_client = client.post(
        "/chat",
        json={"message": "hello"},
        headers={"CF-Connecting-IP": "192.0.2.26"},
        environ_base={"REMOTE_ADDR": "10.0.0.1"},
    )
    assert separate_client.status_code == 500


def test_provider_timeout_returns_safe_error_without_exposing_details(monkeypatch, caplog):
    class _TimeoutGroq:
        def __init__(self, api_key, **kwargs):
            self.chat = self

        @property
        def completions(self):
            return self

        def create(self, **kwargs):
            raise TimeoutError("provider-timeout-internal-detail")

    monkeypatch.setenv("GROQ_API_KEY", "test-key-not-real")
    monkeypatch.setattr(App, "Groq", _TimeoutGroq)
    caplog.set_level(logging.ERROR)

    response = App.app.test_client().post(
        "/chat", json={"message": "Please help me plan home maintenance"}
    )

    assert response.status_code == 500
    body = response.get_data(as_text=True)
    assert "could not complete the request" in body.lower()
    assert "provider-timeout-internal-detail" not in body
    assert "test-key-not-real" not in body
    assert response.get_json()["request_id"]
    assert "provider-timeout-internal-detail" not in caplog.text


def test_rate_limit_expires_at_exact_window_boundary(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    now = [1000.0]
    monkeypatch.setattr(App.time, "monotonic", lambda: now[0])
    client = App.app.test_client()
    address = {"REMOTE_ADDR": "192.0.2.40"}

    for _ in range(App.RATE_LIMIT_REQUESTS):
        assert client.post("/chat", json={"message": "hello"}, environ_base=address).status_code == 500

    assert client.post("/chat", json={"message": "hello"}, environ_base=address).status_code == 429

    now[0] = 1059.999
    assert client.post("/chat", json={"message": "hello"}, environ_base=address).status_code == 429

    now[0] = 1060.0
    assert client.post("/chat", json={"message": "hello"}, environ_base=address).status_code == 500


def test_rate_limit_concurrent_requests_never_exceed_ten_allowed(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    headers = {"CF-Connecting-IP": "192.0.2.41"}
    environ = {"REMOTE_ADDR": "10.0.0.1"}

    def send_request(_index):
        with App.app.test_client() as client:
            response = client.post(
                "/chat",
                json={"message": "hello"},
                headers=headers,
                environ_base=environ,
            )
            return response.status_code

    with ThreadPoolExecutor(max_workers=20) as executor:
        statuses = list(executor.map(send_request, range(20)))

    assert statuses.count(500) == App.RATE_LIMIT_REQUESTS
    assert statuses.count(429) == 20 - App.RATE_LIMIT_REQUESTS


def test_rate_limit_identity_can_be_changed_by_spoofed_cloudflare_header(monkeypatch):
    """A local Flask test client bypasses Cloudflare and can set this header.

    This demonstrates the test-server boundary only; it is not evidence that
    a public Render caller can override Cloudflare's edge-supplied header.
    """
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    client = App.app.test_client()

    # Same WSGI peer address, but each request supplies a different claimed
    # Cloudflare client address. All requests bypass the per-key threshold.
    statuses = [
        client.post(
            "/chat",
            json={"message": "hello"},
            headers={"CF-Connecting-IP": f"198.51.100.{index}"},
            environ_base={"REMOTE_ADDR": "10.0.0.1"},
        ).status_code
        for index in range(1, 12)
    ]

    assert statuses == [500] * 11
    assert len(App._request_history) == 11


def test_rate_limit_tracking_capacity_evicts_oldest_key(monkeypatch):
    monkeypatch.setattr(App, "MAX_TRACKED_CLIENTS", 2)
    App._request_history.clear()

    for address in ("192.0.2.51", "192.0.2.52", "192.0.2.53"):
        with App.app.test_request_context(
            "/chat", headers={"CF-Connecting-IP": address}
        ):
            assert App._chat_rate_limit_exceeded() is False

    assert len(App._request_history) == 2
    assert "192.0.2.51" not in App._request_history
    assert list(App._request_history) == ["192.0.2.52", "192.0.2.53"]


def test_expired_client_history_is_not_swept_for_inactive_clients(monkeypatch):
    now = [1000.0]
    monkeypatch.setattr(App.time, "monotonic", lambda: now[0])
    App._request_history.clear()

    with App.app.test_request_context(
        "/chat", headers={"CF-Connecting-IP": "192.0.2.61"}
    ):
        assert App._chat_rate_limit_exceeded() is False

    now[0] = 1061.0
    with App.app.test_request_context(
        "/chat", headers={"CF-Connecting-IP": "192.0.2.62"}
    ):
        assert App._chat_rate_limit_exceeded() is False

    assert "192.0.2.61" in App._request_history
    # Only the current client's history is pruned; inactive keys remain stale.\n    assert len(App._request_history["192.0.2.61"]) == 1




def test_invalid_cloudflare_ip_header_has_no_trusted_client_key():
    with App.app.test_request_context(
        "/chat",
        headers={
            "CF-Connecting-IP": "not-an-ip, 198.51.100.1",
            "X-Forwarded-For": "203.0.113.99",
        },
        environ_base={"REMOTE_ADDR": "192.0.2.70"},
    ):
        assert App._get_rate_limit_client_key() is None


def test_missing_cloudflare_ip_header_has_no_trusted_client_key():
    with App.app.test_request_context(
        "/chat",
        headers={
            "X-Forwarded-For": "203.0.113.99",
            "TEST-OMIT-CF-HEADER": "1",
        },
        environ_base={"REMOTE_ADDR": "192.0.2.71"},
    ):
        assert App._get_rate_limit_client_key() is None


def test_cloudflare_ipv6_address_is_canonicalized():
    with App.app.test_request_context(
        "/chat",
        headers={"CF-Connecting-IP": "2001:0db8:0000:0000:0000:0000:0000:0001"},
        environ_base={"REMOTE_ADDR": "10.0.0.1"},
    ):
        assert App._get_rate_limit_client_key() == "2001:db8::1"



def test_chat_fails_closed_when_cloudflare_ip_header_is_missing():
    response = App.app.test_client().post(
        "/chat",
        json={"message": "hello"},
        headers={"X-Forwarded-For": "203.0.113.99"},
    )
    assert response.status_code == 503
    assert response.headers["Retry-After"] == "60"
    assert "cannot verify the request source" in response.get_json()["error"]


def test_chat_fails_closed_when_cloudflare_ip_header_is_invalid():
    response = App.app.test_client().post(
        "/chat",
        json={"message": "hello"},
        headers={"CF-Connecting-IP": "not-an-ip, 198.51.100.1"},
        environ_base={"REMOTE_ADDR": "192.0.2.70"},
    )
    assert response.status_code == 503
    assert "cannot verify the request source" in response.get_json()["error"]
