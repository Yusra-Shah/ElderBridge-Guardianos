"""
Tests for the 4 on-device failure fixes.

FIX 1: No photo/upload language in any response
FIX 2: PFTP-style prize+registration scam detected
FIX 3: Chat instant answer for gov.pk authenticity
FIX 4: OTP hallucination stripped from document responses

Run from backend/:
    pytest tests/test_v051_fixes.py -v
"""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from agents.chat_handler import handle_chat_question, _check_website_authenticity
from agents.form_cache import check_form_cache
from agents.fraud_detector import detect_financial_fraud
from graph.build_graph import run_graph
from graph.nodes import _enforce_quality
from main import app
from schemas.decision_schema import FinalDecision, RiskLevel
from schemas.event_schema import EventType, IncomingEvent

client = TestClient(app, raise_server_exceptions=False)


def _make_event(event_type, text, source_app="test.app", user_id="usr_v051"):
    return IncomingEvent(
        event_type=event_type, source_app=source_app,
        redacted_text=text, timestamp=datetime.now(timezone.utc), user_id=user_id,
    )


# =========================================================================
# FIX 1: No photo/upload language
# =========================================================================

class TestNoPhotoLanguage:

    def test_sspa_cache_no_photo(self):
        r = check_form_cache("Sindh Senior Citizen Card application")
        assert r is not None
        assert "photo" not in r.response_text.lower()

    def test_nadra_cache_no_photo(self):
        r = check_form_cache("NADRA CNIC Application renewal form")
        assert r is not None
        assert "photo" not in r.response_text.lower()

    def test_quality_enforcer_strips_photo_language(self):
        text = "Fill the form. Share a clear photo of your CNIC. Then submit."
        result = _enforce_quality(text, "default", "some screen text")
        assert "photo" not in result.lower()

    def test_quality_enforcer_strips_upload_language(self):
        text = "Upload a picture of your documents. Then continue."
        result = _enforce_quality(text, "default", "some screen text")
        assert "upload a picture" not in result.lower()


# =========================================================================
# FIX 2: PFTP-style prize+registration scam
# =========================================================================

class TestPFTPScamDetection:

    def test_pftp_message_detected(self):
        text = (
            "You're shortlisted for Cash prize and internship. "
            "1 time registration. Last day. Classes are active. "
            "Azadi promo:pftp14. pfptedu.org/registration"
        )
        assert detect_financial_fraud(text) is True

    def test_prize_plus_registration_fee(self):
        assert detect_financial_fraud(
            "Congratulations you are shortlisted for cash prize. "
            "Pay registration fee to claim."
        ) is True

    def test_fake_opportunity_plus_fee(self):
        assert detect_financial_fraud(
            "Earn from home Rs 5000 daily. Online earning opportunity. "
            "Pay advance fee of Rs 500 to start."
        ) is True

    def test_legitimate_internship_not_flagged(self):
        assert detect_financial_fraud(
            "Government of Pakistan internship program applications open. "
            "Apply through the official portal. No fee required."
        ) is False

    def test_pftp_via_api(self):
        resp = client.post("/analyze-event", json={
            "event_type": "SMS",
            "source_app": "com.android.messaging",
            "redacted_text": (
                "You're shortlisted for Cash prize and internship. "
                "1 time registration. Last day. pfptedu.org/registration"
            ),
            "timestamp": "2026-06-21T10:00:00Z",
            "user_id": "usr_pftp",
        })
        assert resp.status_code == 200
        assert resp.json()["risk_flag"] == "stop_and_verify"


# =========================================================================
# FIX 3: Chat instant answer for website authenticity
# =========================================================================

class TestChatWebsiteAuthenticity:

    def test_gov_pk_gets_instant_yes(self):
        result = _check_website_authenticity(
            "Is this website authentic?",
            "swd.sindh.gov.pk Social Welfare Department Sindh Senior Citizen Card",
        )
        assert result is not None
        assert result.risk_flag == RiskLevel.NONE
        assert "yes" in result.response_text.lower()
        assert "gov.pk" in result.response_text.lower()

    def test_fake_domain_gets_instant_no(self):
        result = _check_website_authenticity(
            "Is this website safe?",
            "nadra-renewal-pk.com NADRA CNIC renewal service",
        )
        assert result is not None
        assert result.risk_flag == RiskLevel.STOP_AND_VERIFY
        assert "no" in result.response_text.lower()

    def test_non_authenticity_question_returns_none(self):
        result = _check_website_authenticity(
            "What does attested copy mean?",
            "swd.sindh.gov.pk form",
        )
        assert result is None

    def test_no_screen_context_returns_none(self):
        result = _check_website_authenticity("Is this site real?", "")
        assert result is None

    def test_chat_endpoint_gov_pk(self):
        resp = client.post("/ask-question", json={
            "user_id": "usr_auth",
            "question": "Is this website authentic?",
            "screen_context": "swd.sindh.gov.pk Sindh Social Welfare Department",
        })
        assert resp.status_code == 200
        body = resp.json()
        assert "yes" in body["response_text"].lower()
        assert body["risk_flag"] == "none"

    def test_chat_endpoint_known_official_domain(self):
        resp = client.post("/ask-question", json={
            "user_id": "usr_auth",
            "question": "Is this website safe?",
            "screen_context": "jazz.com.pk Jazz packages and offers",
        })
        assert resp.status_code == 200
        assert "yes" in resp.json()["response_text"].lower()


# =========================================================================
# FIX 4: OTP hallucination stripped from document responses
# =========================================================================

class TestOTPHallucinationStrip:

    def test_otp_removed_when_not_in_event(self):
        text = "Open your email. Prepare the correct email address and the OTP shown. Then submit."
        result = _enforce_quality(text, "default", "AKU Lab Report Email from lab@aku.edu")
        assert "otp" not in result.lower()

    def test_otp_preserved_when_in_event(self):
        text = "Enter the OTP to verify your identity."
        result = _enforce_quality(text, "default", "Enter your OTP now to claim benefits")
        assert "otp" in result.lower()

    def test_lab_report_no_otp_via_api(self):
        resp = client.post("/analyze-event", json={
            "event_type": "DOCUMENT",
            "source_app": "com.google.android.gm",
            "redacted_text": (
                "From: lab@aku.edu Subject: Your Lab Report. "
                "Aga Khan University Hospital Laboratory. "
                "Patient Name: [REDACTED]. Test: Complete Blood Count. "
                "Result: Hemoglobin 13.5 g/dL (Normal). "
                "Please consult your doctor for interpretation."
            ),
            "timestamp": "2026-06-21T10:00:00Z",
            "user_id": "usr_lab",
        })
        assert resp.status_code == 200
        text = resp.json()["response_text"].lower()
        assert "otp" not in text

    def test_no_photo_in_form_cache_responses(self):
        """Verify every form cache response is free of photo language."""
        from agents.form_cache import _KNOWN_FORMS
        for form in _KNOWN_FORMS:
            text = form["response"].response_text.lower()
            assert "share a photo" not in text, f"{form['name']} mentions share a photo"
            assert "upload a photo" not in text, f"{form['name']} mentions upload a photo"
            assert "take a photo" not in text, f"{form['name']} mentions take a photo"
