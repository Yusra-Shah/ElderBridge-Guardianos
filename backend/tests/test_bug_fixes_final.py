"""
Tests for the two on-device bugs: chat 422 and lab report false positive.

BUG 1: /ask-question must accept snake_case fields (user_id, screen_context, messages)
BUG 2: AKU lab report DOCUMENT must return risk_flag none, not stop_and_verify

Run from backend/:
    pytest tests/test_bug_fixes_final.py -v
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from graph.build_graph import run_graph
from main import app
from schemas.decision_schema import RiskLevel
from schemas.event_schema import EventType, IncomingEvent

client = TestClient(app, raise_server_exceptions=False)


def _make_event(event_type, text, source_app="test.app", user_id="usr_bugfix"):
    return IncomingEvent(
        event_type=event_type, source_app=source_app,
        redacted_text=text, timestamp=datetime.now(timezone.utc), user_id=user_id,
    )


# =========================================================================
# BUG 1: /ask-question accepts request with user_id + messages + screen_context
# =========================================================================

class TestChatEndpointAcceptsRequest:

    def test_multi_turn_returns_200(self):
        resp = client.post("/ask-question", json={
            "user_id": "usr_chat_bug",
            "messages": [
                {"role": "user", "content": "What does attested copy mean?"}
            ],
            "screen_context": "SSPA Senior Citizen Card form",
        })
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        body = resp.json()
        assert "response_text" in body
        assert "risk_flag" in body

    def test_multi_turn_with_history_returns_200(self):
        resp = client.post("/ask-question", json={
            "user_id": "usr_chat_bug2",
            "messages": [
                {"role": "user", "content": "What is CNIC?"},
                {"role": "assistant", "content": "CNIC is your national identity card."},
                {"role": "user", "content": "Thank you!"},
            ],
            "screen_context": "",
        })
        assert resp.status_code == 200

    def test_empty_messages_with_question_returns_200(self):
        resp = client.post("/ask-question", json={
            "user_id": "usr_chat_bug3",
            "messages": [],
            "screen_context": "",
            "question": "What is NADRA?",
        })
        assert resp.status_code == 200

    def test_missing_screen_context_returns_200(self):
        resp = client.post("/ask-question", json={
            "user_id": "usr_chat_bug4",
            "messages": [
                {"role": "user", "content": "Hello"}
            ],
        })
        assert resp.status_code == 200


# =========================================================================
# BUG 2: AKU lab report DOCUMENT must not be scam-flagged
# =========================================================================

class TestLabReportNotFlagged:

    def test_aku_lab_report_returns_none(self):
        resp = client.post("/analyze-event", json={
            "event_type": "DOCUMENT",
            "source_app": "com.google.android.gm",
            "redacted_text": (
                "From: clinicallab@aku.edu Subject: Your Lab Report Results. "
                "Aga Khan University Hospital Clinical Laboratory. "
                "Patient Name: [REDACTED]. MR Number: 12345678. "
                "Specimen: Blood. Test: Complete Blood Count CBC. "
                "Urine Complete Examination UCS. "
                "Hemoglobin: 13.5 g/dL Normal Range 13.0 to 17.0. "
                "OTP verification may be required to download full report."
            ),
            "timestamp": "2026-06-21T10:00:00Z",
            "user_id": "usr_lab_bug",
        })
        assert resp.status_code == 200
        body = resp.json()
        assert body["risk_flag"] != "stop_and_verify", (
            f"Lab report must NOT be stop_and_verify, got: {body['risk_flag']}"
        )

    def test_lab_report_via_run_graph(self):
        event = _make_event(
            EventType.DOCUMENT,
            "Hospital Laboratory. Patient Name. Specimen Blood. Test result CBC. "
            "OTP may be needed to access patient portal.",
            source_app="com.google.android.gm",
        )
        decision = run_graph(event)
        assert decision.risk_flag != RiskLevel.STOP_AND_VERIFY

    def test_medical_prescription_not_flagged(self):
        event = _make_event(
            EventType.DOCUMENT,
            "Prescription. Dr Ahmed Khan. Diagnosis: Hypertension. "
            "Password protected PDF. Download from clinic portal.",
            source_app="com.google.android.gm",
        )
        decision = run_graph(event)
        assert decision.risk_flag != RiskLevel.STOP_AND_VERIFY

    def test_bank_statement_with_transfer_not_flagged(self):
        event = _make_event(
            EventType.DOCUMENT,
            "Bank Statement June 2026. Salary slip. Credit transfer received. "
            "Balance Rs 50000.",
            source_app="com.google.android.gm",
        )
        decision = run_graph(event)
        assert decision.risk_flag != RiskLevel.STOP_AND_VERIFY

    def test_scam_sms_still_flagged(self):
        """Safe-document bypass must NOT weaken scam detection on SMS."""
        event = _make_event(
            EventType.SMS,
            "Enter your OTP immediately to avoid account suspension.",
            source_app="com.android.messaging",
        )
        decision = run_graph(event)
        assert decision.risk_flag == RiskLevel.STOP_AND_VERIFY
