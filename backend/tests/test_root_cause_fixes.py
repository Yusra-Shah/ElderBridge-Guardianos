"""
Tests for the two root cause fixes.

RC1: Chat retries without screen_context on ContentFilterError
RC2: Safe-document guard forces risk_flag=none on DOCUMENT with safe context

Run from backend/:
    pytest tests/test_root_cause_fixes.py -v
"""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from agents.chat_handler import (
    ContentFilterError,
    handle_chat_question,
    _CHAT_CONTENT_FILTER_FALLBACK,
    _CHAT_FALLBACK,
)
from graph.build_graph import run_graph
from llm.client import sanitize_for_llm
from main import app
from schemas.decision_schema import RiskLevel
from schemas.event_schema import EventType, IncomingEvent

client = TestClient(app, raise_server_exceptions=False)


def _make_event(event_type, text, source_app="test.app", user_id="usr_rc"):
    return IncomingEvent(
        event_type=event_type, source_app=source_app,
        redacted_text=text, timestamp=datetime.now(timezone.utc), user_id=user_id,
    )


# =========================================================================
# RC1: sanitize_for_llm strips map/social/nav noise
# =========================================================================

class TestSanitizeMapAndSocialNoise:

    def test_strips_leaflet_attribution(self):
        result = sanitize_for_llm("Page content. Leaflet | Map data. More content.")
        assert "leaflet" not in result.lower()

    def test_strips_openstreetmap(self):
        result = sanitize_for_llm("Info here. OpenStreetMap contributors. Done.")
        assert "openstreetmap" not in result.lower()

    def test_strips_no_officials_data(self):
        result = sanitize_for_llm("Contact. No officials data available. No officials data available. Footer.")
        assert "no officials data available" not in result.lower()

    def test_strips_social_media_profiles(self):
        result = sanitize_for_llm("Visit facebook.com/govtsindh and instagram.com/swd_sindh for updates.")
        assert "facebook.com/" not in result
        assert "instagram.com/" not in result

    def test_strips_map_marker(self):
        result = sanitize_for_llm("Location. Map marker at coordinates. Zoom in Zoom out.")
        assert "map marker" not in result.lower()
        assert "zoom in" not in result.lower()

    def test_strips_nav_junk(self):
        result = sanitize_for_llm("Text. share button. bookmark button. more options. Real content.")
        assert "share button" not in result.lower()

    def test_truncates_very_long_urls(self):
        long_url = "https://example.com/" + "a" * 100
        result = sanitize_for_llm(f"Visit {long_url} for info.")
        assert len(result) < len(long_url)

    def test_preserves_meaningful_content(self):
        text = "Sindh Social Welfare Department. Senior Citizen Card. Apply now."
        assert "Senior Citizen Card" in sanitize_for_llm(text)


# =========================================================================
# RC1: Chat retries without screen_context on ContentFilterError
# =========================================================================

class TestChatRetryOnContentFilter:

    def test_retry_returns_answer_not_cold_fallback(self):
        call_count = 0
        def _mock_chat(messages, max_tokens=512):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ContentFilterError("Azure content filter: jailbreak detected")
            return "The Senior Citizen Card helps elderly people get financial support."

        with patch("agents.chat_handler.call_llm_chat", side_effect=_mock_chat):
            result = handle_chat_question(
                messages=[{"role": "user", "content": "What is this page about?"}],
                screen_context="swd.sindh.gov.pk messy nav nav nav leaflet zoom in zoom out",
            )

        assert call_count == 2
        assert result.risk_flag == RiskLevel.NONE
        assert "senior citizen" in result.response_text.lower()
        assert result.response_text != _CHAT_FALLBACK.response_text

    def test_both_fail_returns_warm_fallback(self):
        def _always_fail(messages, max_tokens=512):
            raise ContentFilterError("Azure content filter")

        with patch("agents.chat_handler.call_llm_chat", side_effect=_always_fail):
            result = handle_chat_question(
                messages=[{"role": "user", "content": "Hello"}],
                screen_context="messy text",
            )

        assert result.response_text == _CHAT_CONTENT_FILTER_FALLBACK.response_text
        assert "trouble reading" in result.response_text.lower()
        assert result.response_text != _CHAT_FALLBACK.response_text

    def test_retry_omits_screen_context(self):
        calls = []
        def _capture_chat(messages, max_tokens=512):
            calls.append(messages)
            if len(calls) == 1:
                raise ContentFilterError("content_filter")
            return "Here is the answer."

        with patch("agents.chat_handler.call_llm_chat", side_effect=_capture_chat):
            handle_chat_question(
                messages=[{"role": "user", "content": "What is this?"}],
                screen_context="messy screen dump text",
            )

        assert len(calls) == 2
        first_system = calls[0][0]["content"]
        retry_system = calls[1][0]["content"]
        assert "messy screen dump" in first_system
        assert "messy screen dump" not in retry_system


# =========================================================================
# RC2: Safe-document guard forces risk_flag=none for lab reports
# =========================================================================

class TestSafeDocumentGuard:

    def test_aku_lab_report_final_decision_is_none(self):
        event = _make_event(
            EventType.DOCUMENT,
            "Aga Khan University Hospital Clinical Laboratory. "
            "Patient Name [REDACTED]. Specimen Blood. Test CBC UCS. "
            "Hemoglobin 13.5. OTP verification required for patient portal.",
            source_app="com.google.android.gm",
        )
        decision = run_graph(event)
        assert decision.risk_flag == RiskLevel.NONE, (
            f"Lab report got {decision.risk_flag}, expected NONE"
        )

    def test_hospital_discharge_not_flagged(self):
        event = _make_event(
            EventType.DOCUMENT,
            "Hospital Discharge Summary. Patient admitted for observation. "
            "Transfer to ward B. Password for patient portal included.",
            source_app="com.google.android.gm",
        )
        decision = run_graph(event)
        assert decision.risk_flag != RiskLevel.STOP_AND_VERIFY

    def test_prescription_not_flagged(self):
        event = _make_event(
            EventType.DOCUMENT,
            "Prescription by Dr Khan. Diagnosis hypertension. "
            "Medicine Amlodipine 5mg. OTP needed for online pharmacy.",
            source_app="com.google.android.gm",
        )
        decision = run_graph(event)
        assert decision.risk_flag != RiskLevel.STOP_AND_VERIFY

    def test_scam_sms_still_flagged(self):
        """The document guard must NOT affect SMS scam detection."""
        event = _make_event(
            EventType.SMS,
            "Enter your OTP immediately to avoid account suspension.",
            source_app="com.android.messaging",
        )
        decision = run_graph(event)
        assert decision.risk_flag == RiskLevel.STOP_AND_VERIFY

    def test_api_aku_lab_report_returns_none(self):
        resp = client.post("/analyze-event", json={
            "event_type": "DOCUMENT",
            "source_app": "com.google.android.gm",
            "redacted_text": (
                "Clinical Laboratory Aga Khan University Hospital. "
                "Patient Name [REDACTED]. Specimen Blood. Test UCS. "
                "Hemoglobin 13.5. OTP may be needed for portal access."
            ),
            "timestamp": "2026-06-21T10:00:00Z",
            "user_id": "usr_lab_rc",
        })
        assert resp.status_code == 200
        body = resp.json()
        assert body["risk_flag"] != "stop_and_verify", (
            f"API lab report got {body['risk_flag']}, expected NOT stop_and_verify"
        )
        assert "private information" not in body["response_text"].lower()

    def test_university_document_not_flagged(self):
        event = _make_event(
            EventType.DOCUMENT,
            "University of Punjab. Fee Challan. Examination June 2026. "
            "Transfer fee to account. Password for student portal.",
            source_app="com.android.chrome",
        )
        decision = run_graph(event)
        assert decision.risk_flag != RiskLevel.STOP_AND_VERIFY
