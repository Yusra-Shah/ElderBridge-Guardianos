"""
Tests for v0.5.0 expansions: form cache, phishing domains, fraud patterns,
safe-app list, US context, /health capabilities.

Run from backend/:
    pytest tests/test_v050_expansions.py -v
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from agents.form_cache import check_form_cache
from agents.fraud_detector import detect_financial_fraud
from agents.phishing_detector import detect_phishing
from agents.us_context import get_us_analogy, US_ANALOGIES
from graph.build_graph import run_graph
from main import app, _VERSION
from schemas.decision_schema import FinalDecision, RiskLevel
from schemas.event_schema import EventType, IncomingEvent

client = TestClient(app, raise_server_exceptions=False)


def _make_event(event_type, text, source_app="test.app", user_id="usr_v050"):
    return IncomingEvent(
        event_type=event_type, source_app=source_app,
        redacted_text=text, timestamp=datetime.now(timezone.utc), user_id=user_id,
    )


# =========================================================================
# TASK 1+7: Version and /health capabilities
# =========================================================================

class TestVersionAndHealth:

    def test_version_is_050(self):
        assert _VERSION == "0.5.0"

    def test_health_returns_version(self):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["version"] == "0.5.0"

    def test_health_has_capabilities(self):
        body = client.get("/health").json()
        assert "capabilities" in body
        assert isinstance(body["capabilities"], list)
        assert len(body["capabilities"]) >= 8

    def test_health_capabilities_include_key_detectors(self):
        caps = client.get("/health").json()["capabilities"]
        assert "investment_fraud_detection" in caps
        assert "phishing_site_detection" in caps
        assert "emergency_scam_detection" in caps
        assert "prize_lottery_scam_detection" in caps
        assert "government_form_assistance" in caps
        assert "banking_app_safe_bypass" in caps
        assert "chat_question_answering" in caps
        assert "low_signal_filtering" in caps


# =========================================================================
# TASK 2: Expanded form cache
# =========================================================================

class TestExpandedFormCache:

    def test_watan_card(self):
        result = check_form_cache("Watan Card registration for flood relief Sindh families")
        assert result is not None
        assert result.risk_flag == RiskLevel.NONE
        assert "watan" in result.response_text.lower() or "flood" in result.response_text.lower()

    def test_zakat_program(self):
        result = check_form_cache("Government Zakat and Ushr Department for mustahiq families")
        assert result is not None
        assert "zakat" in result.response_text.lower()

    def test_eobi_pension(self):
        result = check_form_cache("EOBI Employees Old-Age Benefits pension claim form")
        assert result is not None
        assert "eobi" in result.response_text.lower() or "pension" in result.response_text.lower()

    def test_sehat_sahulat(self):
        result = check_form_cache("Sehat Sahulat health card registration hospital")
        assert result is not None
        assert "sehat" in result.response_text.lower() or "health" in result.response_text.lower()

    def test_kisan_card(self):
        result = check_form_cache("Punjab Kisan Card registration for agriculture subsidy")
        assert result is not None
        assert "kisan" in result.response_text.lower() or "farmer" in result.response_text.lower()

    def test_hec_scholarship(self):
        result = check_form_cache("HEC Higher Education Commission scholarship form application")
        assert result is not None
        assert "hec" in result.response_text.lower() or "scholarship" in result.response_text.lower()

    def test_pensioner_portal(self):
        result = check_form_cache("Pensioner payment status retired government GPF balance")
        assert result is not None
        assert "pension" in result.response_text.lower()

    def test_original_sspa_still_works(self):
        result = check_form_cache("Sindh Senior Citizen Card application")
        assert result is not None
        assert "sindh" in result.response_text.lower()

    def test_original_nadra_still_works(self):
        result = check_form_cache("NADRA CNIC renewal application form")
        assert result is not None


# =========================================================================
# TASK 3: Expanded phishing domains
# =========================================================================

class TestExpandedPhishingDomains:

    def test_fake_fbr_detected(self):
        assert detect_phishing(
            "fbr-taxportal.com FBR Tax Return. Enter CNIC. Processing fee Rs 1000.",
            "com.android.chrome",
        ) is True

    def test_real_fbr_passes(self):
        assert detect_phishing(
            "iris.fbr.gov.pk FBR Tax Return. Enter details.",
            "com.android.chrome",
        ) is False

    def test_fake_jazz_detected(self):
        assert detect_phishing(
            "jazz-rewards.net Jazz free data offer. Enter CNIC to claim. Fee Rs 50.",
            "com.android.chrome",
        ) is True

    def test_real_jazz_passes(self):
        assert detect_phishing(
            "jazz.com.pk Jazz packages and offers.",
            "com.android.chrome",
        ) is False

    def test_fake_sbp_detected(self):
        assert detect_phishing(
            "sbp-update.com State Bank SBP account verification. CNIC required. Fee Rs 200.",
            "com.android.chrome",
        ) is True

    def test_fake_telenor_detected(self):
        assert detect_phishing(
            "telenor-pk-offers.com Telenor SIM verification. Enter CNIC for activation.",
            "com.android.chrome",
        ) is True


# =========================================================================
# TASK 4: Expanded safe-app bypass
# =========================================================================

class TestExpandedSafeApps:

    def test_meezan_bank_not_flagged(self):
        event = _make_event(EventType.FORM_SCREEN,
                            "Meezan Bank Login. Username. Password. Login.",
                            source_app="com.meezan.bank")
        decision = run_graph(event)
        assert decision.risk_flag != RiskLevel.STOP_AND_VERIFY

    def test_allied_bank_not_flagged(self):
        event = _make_event(EventType.FORM_SCREEN,
                            "Allied Bank Digital. Username. Password. Login.",
                            source_app="com.abl.digitalabl")
        decision = run_graph(event)
        assert decision.risk_flag != RiskLevel.STOP_AND_VERIFY

    def test_daraz_not_flagged(self):
        event = _make_event(EventType.FORM_SCREEN,
                            "Daraz Shopping. Cart. Payment. Transfer. Checkout.",
                            source_app="com.daraz.android")
        decision = run_graph(event)
        assert decision.risk_flag != RiskLevel.STOP_AND_VERIFY


# =========================================================================
# TASK 5: US context
# =========================================================================

class TestUSContext:

    def test_analogies_dict_has_entries(self):
        assert len(US_ANALOGIES) >= 12

    def test_get_sspa_analogy(self):
        result = get_us_analogy("SSPA Senior Citizen Card")
        assert "social security" in result.lower()

    def test_get_nadra_analogy(self):
        result = get_us_analogy("NADRA CNIC")
        assert "dmv" in result.lower() or "social security" in result.lower()

    def test_get_ehsaas_analogy(self):
        result = get_us_analogy("Ehsaas/BISP")
        assert "snap" in result.lower() or "medicaid" in result.lower()

    def test_get_investment_scam_analogy(self):
        result = get_us_analogy("Investment scam")
        assert "ftc" in result.lower() or "billion" in result.lower()

    def test_get_emergency_scam_analogy(self):
        result = get_us_analogy("Emergency family scam")
        assert "grandparent" in result.lower() or "fbi" in result.lower()

    def test_get_phishing_analogy(self):
        result = get_us_analogy("Phishing government sites")
        assert "irs" in result.lower() or "ssa" in result.lower()

    def test_get_unknown_returns_default(self):
        result = get_us_analogy("Nonexistent Program XYZ")
        assert "no us analogy" in result.lower()


# =========================================================================
# TASK 6: Expanded fraud patterns
# =========================================================================

class TestExpandedFraudPatterns:

    def test_prize_lottery_with_link(self):
        assert detect_financial_fraud(
            "Congratulations! You are the selected winner of our lucky draw. "
            "Claim your prize at https://prize-claim.com/winner"
        ) is True

    def test_banking_impersonation_with_action(self):
        assert detect_financial_fraud(
            "Your account will be blocked due to unusual activity detected "
            "on your account. Click here to verify immediately."
        ) is True

    def test_job_scam_with_fee(self):
        assert detect_financial_fraud(
            "Work from home earn daily Rs 5000 with online typing job. "
            "Pay registration fee of Rs 500 to start."
        ) is True

    def test_legitimate_bank_notification_passes(self):
        assert detect_financial_fraud(
            "Your HBL savings account balance is Rs 50,000. "
            "Last transaction: salary credit."
        ) is False

    def test_legitimate_job_posting_passes(self):
        assert detect_financial_fraud(
            "Government of Pakistan Public Service Commission. "
            "Applications invited for the post of Assistant Director."
        ) is False
