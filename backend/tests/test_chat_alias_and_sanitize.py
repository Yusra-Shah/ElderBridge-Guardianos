"""
Tests for chat alias tolerance and LLM text sanitization.

ISSUE 1: ChatRequest accepts both camelCase and snake_case field names
ISSUE 2: sanitize_for_llm cleans messy accessibility dumps

Run from backend/:
    pytest tests/test_chat_alias_and_sanitize.py -v
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from llm.client import sanitize_for_llm
from main import app

client = TestClient(app, raise_server_exceptions=False)


# =========================================================================
# ISSUE 1: ChatRequest accepts both camelCase and snake_case
# =========================================================================

class TestChatRequestAliases:

    def test_camel_case_accepted(self):
        resp = client.post("/ask-question", json={
            "userId": "usr_camel",
            "messages": [{"role": "user", "content": "Hello"}],
            "screenContext": "Some screen text",
        })
        assert resp.status_code == 200, f"camelCase returned {resp.status_code}: {resp.text}"

    def test_snake_case_accepted(self):
        resp = client.post("/ask-question", json={
            "user_id": "usr_snake",
            "messages": [{"role": "user", "content": "Hello"}],
            "screen_context": "Some screen text",
        })
        assert resp.status_code == 200, f"snake_case returned {resp.status_code}: {resp.text}"

    def test_mixed_case_accepted(self):
        resp = client.post("/ask-question", json={
            "userId": "usr_mixed",
            "messages": [{"role": "user", "content": "Hi"}],
            "screen_context": "text",
        })
        assert resp.status_code == 200

    def test_empty_messages_with_question_returns_200(self):
        resp = client.post("/ask-question", json={
            "user_id": "usr_empty",
            "messages": [],
            "question": "What is CNIC?",
        })
        assert resp.status_code == 200

    def test_empty_messages_no_question_returns_fallback(self):
        resp = client.post("/ask-question", json={
            "user_id": "usr_nothing",
            "messages": [],
            "question": "",
        })
        assert resp.status_code == 200
        assert len(resp.json()["response_text"]) > 0

    def test_missing_screen_context_defaults_empty(self):
        resp = client.post("/ask-question", json={
            "user_id": "usr_nosc",
            "messages": [{"role": "user", "content": "Hello"}],
        })
        assert resp.status_code == 200

    def test_response_has_finaldecision_shape(self):
        resp = client.post("/ask-question", json={
            "userId": "usr_shape",
            "messages": [{"role": "user", "content": "What is NADRA?"}],
        })
        body = resp.json()
        assert "response_text" in body
        assert "risk_flag" in body
        assert "next_steps" in body
        assert "source_citations" in body


# =========================================================================
# ISSUE 2: sanitize_for_llm
# =========================================================================

class TestSanitizeForLLM:

    def test_strips_url_tracking_params(self):
        text = "Visit https://swd.sindh.gov.pk/page?igsh=abc123&utm_source=fb for details"
        result = sanitize_for_llm(text)
        assert "igsh=" not in result
        assert "utm_source" not in result
        assert "swd.sindh.gov.pk" in result

    def test_strips_hash_fragments(self):
        text = "Go to https://example.com/page#section?t=123"
        result = sanitize_for_llm(text)
        assert "#section" not in result

    def test_collapses_duplicate_phrases(self):
        text = "Contact Us Contact Us Home About Programs About Programs"
        result = sanitize_for_llm(text)
        count = result.lower().count("contact us")
        assert count == 1, f"Expected 1 'contact us', got {count}: {result}"

    def test_removes_percent_encoded_chars(self):
        text = "Link: %3D%2F%26 some text"
        result = sanitize_for_llm(text)
        assert "%3D" not in result
        assert "%2F" not in result

    def test_removes_control_characters(self):
        text = "Hello\x00World\x0eTest\x1fEnd"
        result = sanitize_for_llm(text)
        assert "\x00" not in result
        assert "\x0e" not in result
        assert "HelloWorldTestEnd" in result.replace(" ", "")

    def test_normalizes_whitespace(self):
        text = "Hello     World\n\n\n\n\nNext"
        result = sanitize_for_llm(text)
        assert "     " not in result
        assert "\n\n\n" not in result

    def test_preserves_meaningful_content(self):
        text = "Sindh Senior Citizen Card Application Form. Enter your name and CNIC."
        result = sanitize_for_llm(text)
        assert "Sindh Senior Citizen Card" in result
        assert "CNIC" in result

    def test_empty_input(self):
        assert sanitize_for_llm("") == ""
        assert sanitize_for_llm(None) is None

    def test_messy_sspa_dump_survives(self):
        """A realistic messy accessibility dump must not crash and must retain gov.pk domain."""
        dump = (
            "swd.sindh.gov.pk?igsh=abc123&t=share — Social Welfare Department "
            "Government of Sindh Government of Sindh. "
            "Navigation: Home Home About About Programs Programs Contact Contact. "
            "Sindh Senior Citizen Card Application Form. %3D%2F some text. "
            "\x00\x0e  extra   spaces   here. "
            "Footer Footer Copyright 2026."
        )
        result = sanitize_for_llm(dump)
        assert "swd.sindh.gov.pk" in result
        assert "igsh=" not in result
        assert "%3D" not in result
        assert "\x00" not in result
        assert len(result) > 50

    def test_chat_with_messy_screen_context_returns_200(self):
        messy_context = (
            "swd.sindh.gov.pk?igsh=abc&utm_source=fb — Govt of Sindh Govt of Sindh. "
            "Nav: Home Home About About. %3D%2F. \x00 Sindh Senior Citizen Card. "
            "Contact Us Contact Us. Footer Footer."
        )
        resp = client.post("/ask-question", json={
            "user_id": "usr_messy",
            "messages": [{"role": "user", "content": "What is this page?"}],
            "screen_context": messy_context,
        })
        assert resp.status_code == 200
        assert len(resp.json()["response_text"]) > 0
