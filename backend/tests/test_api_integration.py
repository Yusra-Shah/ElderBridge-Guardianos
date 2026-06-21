"""
Integration tests for the ElderBridge FastAPI layer.

These tests exercise the full HTTP stack (routing, serialisation, CORS headers,
error handling) using FastAPI's TestClient — no real network, no real LLM.

The autouse _stub_llm_offline fixture in conftest.py keeps all tests offline by
patching agents.benefits_agent.call_llm with a safe canned response.

Test groups:
  1. Health endpoint         — GET /health returns 200 with expected fields
  2. FORM_SCREEN happy path  — valid payload returns 200 + FinalDecision shape
  3. Scam SMS guardrail      — OTP SMS payload returns stop_and_verify risk flag
  4. Input validation        — empty / missing fields return 422
  5. CORS headers            — preflight and response carry correct CORS headers
  6. FinalDecision shape     — response JSON matches the documented schema

Run from backend/:
    pytest tests/test_api_integration.py -v
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from main import app, _VERSION

client = TestClient(app, raise_server_exceptions=True)

# ---------------------------------------------------------------------------
# Shared test payloads
# ---------------------------------------------------------------------------

_FORM_SCREEN_PAYLOAD = {
    "event_type": "FORM_SCREEN",
    "source_app": "gov.benefits.portal",
    "redacted_text": "What is your monthly household income? Please enter in PKR.",
    "timestamp": "2026-06-15T10:00:00Z",
    "user_id": "usr_integration_test_01",
}

_SCAM_SMS_PAYLOAD = {
    "event_type": "SMS",
    "source_app": "com.android.messaging",
    "redacted_text": (
        "Congratulations! Your senior healthcare grant has been approved. "
        "Enter your OTP now to claim Rs.50,000 benefit immediately."
    ),
    "timestamp": "2026-06-15T10:01:00Z",
    "user_id": "usr_integration_test_02",
}

_BENIGN_DOCUMENT_PAYLOAD = {
    "event_type": "DOCUMENT",
    "source_app": "com.google.android.documentsui",
    "redacted_text": "Dear resident, please find enclosed your updated address record for the current year.",
    "timestamp": "2026-06-15T10:02:00Z",
    "user_id": "usr_integration_test_03",
}

_NOTIFICATION_PAYLOAD = {
    "event_type": "NOTIFICATION",
    "source_app": "pk.nadra.online",
    "redacted_text": "Your NADRA application has been received. Processing time is 7-10 working days.",
    "timestamp": "2026-06-15T10:03:00Z",
    "user_id": "usr_integration_test_04",
}


# ---------------------------------------------------------------------------
# Test Group 1 — Health endpoint
# ---------------------------------------------------------------------------

class TestHealthEndpoint:

    def test_health_returns_200(self):
        resp = client.get("/health")
        assert resp.status_code == 200

    def test_health_returns_status_ok(self):
        resp = client.get("/health")
        assert resp.json()["status"] == "ok"

    def test_health_returns_version(self):
        resp = client.get("/health")
        assert resp.json()["version"] == _VERSION

    def test_health_returns_timestamp(self):
        resp = client.get("/health")
        body = resp.json()
        assert "timestamp" in body
        assert len(body["timestamp"]) > 0


# ---------------------------------------------------------------------------
# Test Group 2 — FORM_SCREEN happy path
# ---------------------------------------------------------------------------

class TestFormScreenHappyPath:

    def test_form_screen_returns_200(self):
        resp = client.post("/analyze-event", json=_FORM_SCREEN_PAYLOAD)
        assert resp.status_code == 200

    def test_form_screen_returns_valid_json(self):
        resp = client.post("/analyze-event", json=_FORM_SCREEN_PAYLOAD)
        body = resp.json()
        assert isinstance(body, dict)

    def test_form_screen_response_has_response_text(self):
        resp = client.post("/analyze-event", json=_FORM_SCREEN_PAYLOAD)
        body = resp.json()
        assert "response_text" in body
        assert len(body["response_text"]) > 0

    def test_form_screen_response_has_risk_flag(self):
        resp = client.post("/analyze-event", json=_FORM_SCREEN_PAYLOAD)
        body = resp.json()
        assert "risk_flag" in body
        valid_flags = {
            "none", "silent", "soft_help", "caution",
            "verify_first", "stop_and_verify", "contact_trusted_person",
        }
        assert body["risk_flag"] in valid_flags

    def test_form_screen_response_has_next_steps(self):
        resp = client.post("/analyze-event", json=_FORM_SCREEN_PAYLOAD)
        body = resp.json()
        assert "next_steps" in body
        assert isinstance(body["next_steps"], list)

    def test_form_screen_response_has_source_citations(self):
        resp = client.post("/analyze-event", json=_FORM_SCREEN_PAYLOAD)
        body = resp.json()
        assert "source_citations" in body
        assert isinstance(body["source_citations"], list)

    def test_benign_income_form_is_low_risk(self):
        """A plain income field should be NONE or SILENT — never STOP_AND_VERIFY."""
        resp = client.post("/analyze-event", json=_FORM_SCREEN_PAYLOAD)
        assert resp.json()["risk_flag"] in ("none", "silent", "soft_help")

    def test_benign_document_is_low_risk(self):
        resp = client.post("/analyze-event", json=_BENIGN_DOCUMENT_PAYLOAD)
        assert resp.json()["risk_flag"] in ("none", "silent", "soft_help", "caution")


# ---------------------------------------------------------------------------
# Test Group 3 — Scam SMS triggers guardrail
# ---------------------------------------------------------------------------

class TestScamSmsGuardrail:

    def test_otp_sms_returns_200(self):
        resp = client.post("/analyze-event", json=_SCAM_SMS_PAYLOAD)
        assert resp.status_code == 200

    def test_otp_sms_returns_stop_and_verify(self):
        """OTP in SMS text must trigger STOP_AND_VERIFY risk flag."""
        resp = client.post("/analyze-event", json=_SCAM_SMS_PAYLOAD)
        assert resp.json()["risk_flag"] == "stop_and_verify"

    def test_blocked_response_has_safe_text(self):
        """Scam response must be non-empty and must not instruct the user to share OTP."""
        resp = client.post("/analyze-event", json=_SCAM_SMS_PAYLOAD)
        body = resp.json()
        assert len(body["response_text"]) > 0
        text = body["response_text"].lower()
        assert "enter your otp" not in text
        assert "share your otp" not in text

    def test_blocked_response_has_next_steps(self):
        resp = client.post("/analyze-event", json=_SCAM_SMS_PAYLOAD)
        assert len(resp.json()["next_steps"]) > 0

    def test_blocked_source_citations_empty(self):
        """Guardrail block must not attach evidence citations."""
        resp = client.post("/analyze-event", json=_SCAM_SMS_PAYLOAD)
        assert resp.json()["source_citations"] == []


# ---------------------------------------------------------------------------
# Test Group 4 — Input validation
# ---------------------------------------------------------------------------

class TestInputValidation:

    def test_empty_redacted_text_returns_422(self):
        payload = {**_FORM_SCREEN_PAYLOAD, "redacted_text": "   "}
        resp = client.post("/analyze-event", json=payload)
        assert resp.status_code == 422

    def test_missing_event_type_returns_422(self):
        payload = {k: v for k, v in _FORM_SCREEN_PAYLOAD.items() if k != "event_type"}
        resp = client.post("/analyze-event", json=payload)
        assert resp.status_code == 422

    def test_missing_redacted_text_returns_422(self):
        payload = {k: v for k, v in _FORM_SCREEN_PAYLOAD.items() if k != "redacted_text"}
        resp = client.post("/analyze-event", json=payload)
        assert resp.status_code == 422

    def test_invalid_event_type_returns_422(self):
        payload = {**_FORM_SCREEN_PAYLOAD, "event_type": "INVALID_TYPE"}
        resp = client.post("/analyze-event", json=payload)
        assert resp.status_code == 422

    def test_empty_body_returns_422(self):
        resp = client.post("/analyze-event", json={})
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Test Group 5 — CORS headers
# ---------------------------------------------------------------------------

class TestCORSHeaders:

    def test_options_preflight_returns_200(self):
        """Android Retrofit/OkHttp may send a preflight OPTIONS request."""
        resp = client.options(
            "/analyze-event",
            headers={
                "Origin": "http://192.168.1.10",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "Content-Type",
            },
        )
        assert resp.status_code == 200

    def test_cors_allow_origin_header_present(self):
        """The response must carry an Access-Control-Allow-Origin header."""
        resp = client.post(
            "/analyze-event",
            json=_FORM_SCREEN_PAYLOAD,
            headers={"Origin": "http://192.168.1.10"},
        )
        assert "access-control-allow-origin" in resp.headers

    def test_health_has_cors_allow_origin(self):
        resp = client.get("/health", headers={"Origin": "http://192.168.1.10"})
        assert "access-control-allow-origin" in resp.headers


# ---------------------------------------------------------------------------
# Test Group 6 — FinalDecision shape (contract test for Android)
# ---------------------------------------------------------------------------

class TestFinalDecisionShape:
    """These tests pin the exact JSON shape the Android app will consume."""

    def test_notification_payload_returns_finaldecision(self):
        resp = client.post("/analyze-event", json=_NOTIFICATION_PAYLOAD)
        assert resp.status_code == 200
        body = resp.json()
        # Mandatory top-level keys
        assert "response_text" in body
        assert "risk_flag" in body
        assert "next_steps" in body
        assert "source_citations" in body

    def test_response_text_is_string(self):
        resp = client.post("/analyze-event", json=_NOTIFICATION_PAYLOAD)
        assert isinstance(resp.json()["response_text"], str)

    def test_next_steps_items_are_strings(self):
        resp = client.post("/analyze-event", json=_NOTIFICATION_PAYLOAD)
        for step in resp.json()["next_steps"]:
            assert isinstance(step, str)

    def test_source_citations_items_have_evidence_fields(self):
        """Each citation object must match the EvidenceItem schema."""
        resp = client.post("/analyze-event", json=_FORM_SCREEN_PAYLOAD)
        for citation in resp.json()["source_citations"]:
            assert "source_id" in citation
            assert "title" in citation
            assert "tier" in citation
            assert "snippet" in citation
            assert "relevance_score" in citation

    def test_content_type_is_json(self):
        resp = client.post("/analyze-event", json=_FORM_SCREEN_PAYLOAD)
        assert "application/json" in resp.headers["content-type"]
