"""
Tests for Phase 2 agent intelligence upgrades.

Covers: phishing detector, emergency scam detector, safe-app bypass,
prize/lottery escalation, context classification, baseline signals,
guardrail context-aware responses, response quality rules.

Run from backend/:
    pytest tests/test_phase2.py -v
"""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from agents.emergency_scam_detector import detect_emergency_scam
from agents.phishing_detector import detect_phishing
from agents.router_agent import RouterAgent, classify_context, _is_low_signal
from graph.build_graph import run_graph
from graph.nodes import _extract_signals, _enforce_quality
from graph.state import make_initial_state
from main import app
from schemas.decision_schema import FinalDecision, RiskLevel
from schemas.event_schema import EventType, IncomingEvent

client = TestClient(app, raise_server_exceptions=False)


def _make_event(
    event_type: EventType,
    redacted_text: str,
    source_app: str = "test.app",
    user_id: str = "usr_p2_test",
) -> IncomingEvent:
    return IncomingEvent(
        event_type=event_type,
        source_app=source_app,
        redacted_text=redacted_text,
        timestamp=datetime.now(timezone.utc),
        user_id=user_id,
    )


# =========================================================================
# Phishing detector
# =========================================================================

class TestPhishingDetector:

    def test_fake_nadra_site_detected(self):
        assert detect_phishing(
            "nadra-renewal-pk.com NADRA Online CNIC Renewal. Enter CNIC. Processing Fee Rs 500.",
            "com.android.chrome",
        ) is True

    def test_real_nadra_site_not_detected(self):
        assert detect_phishing(
            "nadra.gov.pk NADRA Online CNIC. Enter details.",
            "com.android.chrome",
        ) is False

    def test_non_browser_not_detected(self):
        assert detect_phishing(
            "nadra-fake.com NADRA renewal fee Rs 500 CNIC",
            "com.whatsapp",
        ) is False

    def test_fake_bisp_detected(self):
        assert detect_phishing(
            "bisp-support.net BISP Registration. Enter CNIC. Fee Rs 200.",
            "com.android.chrome",
        ) is True

    def test_gov_pk_domain_passes(self):
        assert detect_phishing(
            "bisp.gov.pk BISP Registration. Enter CNIC details.",
            "com.android.chrome",
        ) is False

    def test_phishing_via_api(self):
        resp = client.post("/analyze-event", json={
            "event_type": "FORM_SCREEN",
            "source_app": "com.android.chrome",
            "redacted_text": (
                "nadra-renewal-pk.com NADRA Online CNIC Renewal Service. "
                "Enter your CNIC Number. Processing Fee: Rs 500."
            ),
            "timestamp": "2026-06-20T10:00:00Z",
            "user_id": "usr_p2_phish",
        })
        assert resp.status_code == 200
        assert resp.json()["risk_flag"] == "stop_and_verify"
        assert "gov.pk" in resp.json()["response_text"].lower()


# =========================================================================
# Emergency scam detector
# =========================================================================

class TestEmergencyScamDetector:

    def test_family_emergency_scam_detected(self):
        assert detect_emergency_scam(
            "I am your nephew Ali. I am in the hospital. "
            "Please send the money urgently Rs 20000. "
            "Do not tell anyone in the family."
        ) is True

    def test_normal_family_message_not_detected(self):
        assert detect_emergency_scam(
            "Assalamualaikum Uncle ji. I am your nephew Ali. "
            "How are you? I will visit next week InshAllah."
        ) is False

    def test_relative_without_money_not_detected(self):
        assert detect_emergency_scam(
            "I am your nephew. I had an accident. Please pray for me."
        ) is False

    def test_money_without_relative_not_detected(self):
        assert detect_emergency_scam(
            "Please send Rs 5000 urgently. Do not tell anyone."
        ) is False

    def test_emergency_via_api(self):
        resp = client.post("/analyze-event", json={
            "event_type": "SMS",
            "source_app": "com.whatsapp",
            "redacted_text": (
                "Uncle ji I am your nephew Ali. Lost my phone abroad. "
                "In hospital after accident. Send Rs 20000 urgently to "
                "JazzCash [REDACTED_PHONE]. Do not tell Ammi."
            ),
            "timestamp": "2026-06-20T10:00:00Z",
            "user_id": "usr_p2_emerg",
        })
        assert resp.status_code == 200
        assert resp.json()["risk_flag"] == "stop_and_verify"
        assert "family" in resp.json()["response_text"].lower() or "relative" in resp.json()["response_text"].lower()


# =========================================================================
# Safe-app bypass
# =========================================================================

class TestSafeAppBypass:

    def test_bank_login_not_flagged(self):
        event = _make_event(
            EventType.FORM_SCREEN,
            "HBL Mobile Banking. Username. Password. Login. Forgot Password.",
            source_app="com.hbl.android.hblpersonal",
        )
        decision = run_graph(event)
        assert decision.risk_flag != RiskLevel.STOP_AND_VERIFY

    def test_easypaisa_not_flagged(self):
        event = _make_event(
            EventType.FORM_SCREEN,
            "Easypaisa Send Money. Amount Rs 5000. Send. Transfer complete.",
            source_app="pk.com.telenor.phoenix",
        )
        decision = run_graph(event)
        assert decision.risk_flag != RiskLevel.STOP_AND_VERIFY

    def test_scam_sms_still_flagged(self):
        """Safe-app bypass must not affect scam SMS from messaging apps."""
        event = _make_event(
            EventType.SMS,
            "Enter your OTP to claim your prize now.",
            source_app="com.android.messaging",
        )
        decision = run_graph(event)
        assert decision.risk_flag == RiskLevel.STOP_AND_VERIFY


# =========================================================================
# Prize/lottery scam escalation
# =========================================================================

class TestPrizeLotteryEscalation:

    def test_lottery_sms_reaches_stop_and_verify(self):
        event = _make_event(
            EventType.SMS,
            "Congratulations! You have been selected in Jazz Lucky Draw. "
            "You won the grand prize. Call to claim your prize within 24 hours.",
            source_app="com.android.messaging",
        )
        decision = run_graph(event)
        assert decision.risk_flag == RiskLevel.STOP_AND_VERIFY

    def test_lottery_response_names_scam_type(self):
        event = _make_event(
            EventType.SMS,
            "You won the grand prize in Lucky Draw. Call now to claim reward.",
            source_app="com.android.messaging",
        )
        decision = run_graph(event)
        text = decision.response_text.lower()
        assert "lottery" in text or "prize" in text or "scam" in text


# =========================================================================
# Context classification
# =========================================================================

class TestContextClassification:

    def test_banking_app_classified(self):
        event = _make_event(EventType.FORM_SCREEN, "Login Password Username",
                            source_app="com.hbl.android.hblpersonal")
        assert classify_context(event) == "banking_app"

    def test_media_app_classified(self):
        event = _make_event(EventType.FORM_SCREEN, "Video title channel views comments",
                            source_app="com.google.android.youtube")
        ctx = classify_context(event)
        assert ctx in ("media_content", "low_signal")

    def test_government_form_classified(self):
        event = _make_event(EventType.FORM_SCREEN, "NADRA CNIC application renewal",
                            source_app="com.android.chrome")
        assert classify_context(event) == "government_form"

    def test_low_signal_classified(self):
        event = _make_event(EventType.FORM_SCREEN, "Home Screen Clock Weather",
                            source_app="com.android.launcher")
        assert classify_context(event) == "low_signal"

    def test_legitimate_sms_classified(self):
        event = _make_event(EventType.SMS, "Your appointment is confirmed for tomorrow.",
                            source_app="com.android.messaging")
        assert classify_context(event) == "legitimate_message"


# =========================================================================
# Baseline signal extraction
# =========================================================================

class TestBaselineSignals:

    def test_extracts_amounts(self):
        signals = _extract_signals("Processing fee Rs 500 and PKR 1000")
        assert len(signals["amounts"]) >= 1

    def test_extracts_urls(self):
        signals = _extract_signals("Visit https://example.com for details")
        assert len(signals["urls"]) >= 1

    def test_extracts_urgency(self):
        signals = _extract_signals("Please respond urgently, this will expire soon")
        assert "urgent" in signals["urgency"] or "expire" in signals["urgency"]

    def test_extracts_personal_fields(self):
        signals = _extract_signals("Enter your CNIC and password to continue")
        assert "cnic" in signals["personal_fields"]
        assert "password" in signals["personal_fields"]


# =========================================================================
# Response quality enforcement
# =========================================================================

class TestResponseQuality:

    def test_under_80_words(self):
        long_text = " ".join(["word"] * 100)
        result = _enforce_quality(long_text, "default")
        assert len(result.split()) <= 81

    def test_low_signal_under_20_words(self):
        text = " ".join(["word"] * 30)
        result = _enforce_quality(text, "low_signal")
        assert len(result.split()) <= 21

    def test_removes_this_screen_opener(self):
        result = _enforce_quality("This screen shows a login form.", "default")
        assert not result.lower().startswith("this screen")

    def test_removes_this_looks_like_opener(self):
        result = _enforce_quality("This looks like a government form.", "default")
        assert not result.lower().startswith("this looks like")

    def test_preserves_normal_opener(self):
        result = _enforce_quality("Please fill in your details.", "default")
        assert result.startswith("Please")


# =========================================================================
# Media content handling
# =========================================================================

class TestMediaHandling:

    def test_youtube_is_low_signal(self):
        assert _is_low_signal(
            "Video title views comments subscribe like share",
            "com.google.android.youtube",
        ) is True

    def test_youtube_routes_empty(self):
        event = _make_event(EventType.FORM_SCREEN,
                            "Video. 5 Simple Exercises. Views 245K. Like Share Save.",
                            source_app="com.google.android.youtube")
        router = RouterAgent()
        assert router.route(event) == []

    def test_youtube_via_api_returns_none_risk(self):
        resp = client.post("/analyze-event", json={
            "event_type": "FORM_SCREEN",
            "source_app": "com.google.android.youtube",
            "redacted_text": "YouTube. Dr Health Pakistan. 5 Exercises for Seniors. Views 245K.",
            "timestamp": "2026-06-20T10:00:00Z",
            "user_id": "usr_p2_yt",
        })
        assert resp.status_code == 200
        body = resp.json()
        assert body["risk_flag"] == "none"
        assert len(body["response_text"]) < 200
