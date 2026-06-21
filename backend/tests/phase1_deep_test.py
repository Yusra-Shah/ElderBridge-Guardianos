"""
Phase 1 — Deep local testing: 10 realistic full-screen scenarios.

Each scenario simulates real full-screen content exactly as the
AccessibilityService would capture from an elderly Pakistani user's phone.

Run standalone:
    cd backend && python tests/phase1_deep_test.py
"""
from __future__ import annotations
import json, sys, os, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from unittest.mock import patch

_LLM = "You may qualify based on the information provided. Please verify with the official agency."
_FORM = "This form asks for your personal details. Fill each field carefully. Ask a trusted person if unsure."
_CHAT = "An attested copy is a certified true copy of a document, stamped by an authorized official like a notary."

with patch("agents.benefits_agent.call_llm_race", return_value=_LLM), \
     patch("agents.form_agent.call_llm_race", return_value=_FORM), \
     patch("agents.chat_handler.call_llm", return_value=_CHAT), \
     patch("agents.benefits_agent.call_llm", return_value=_LLM), \
     patch("agents.form_agent.call_llm", return_value=_FORM):

    from fastapi.testclient import TestClient
    from main import app, _response_cache
    client = TestClient(app, raise_server_exceptions=False)

    SCENARIOS = []

    # ── Scenario 1: SSPA Sindh Senior Citizen Card ──────────────────────────
    SCENARIOS.append({
        "name": "S1  SSPA Sindh Senior Citizen Card",
        "endpoint": "/analyze-event",
        "payload": {
            "event_type": "FORM_SCREEN",
            "source_app": "com.android.chrome",
            "redacted_text": (
                "swd.sindh.gov.pk — Social Welfare Department, Government of Sindh. "
                "Navigation: Home | About | Programs | Contact. "
                "Sindh Senior Citizen Card — Application Form. "
                "The Sindh Social Protection Authority (SSPA) provides financial "
                "assistance to senior citizens aged 60 and above residing in Sindh. "
                "Eligibility Criteria: 1. Must be a permanent resident of Sindh. "
                "2. Age must be 60 years or above. 3. Must hold a valid CNIC. "
                "4. Monthly household income must not exceed Rs 25,000. "
                "Required Documents: Original CNIC (front and back copy), "
                "Two recent passport-size photographs, Domicile certificate of Sindh, "
                "Income certificate from a government-gazetted officer. "
                "How to Apply: Visit your nearest SSPA registration centre with all "
                "documents. Fill in the application form at the centre. Your application "
                "will be verified within 30 working days. Approved applicants will receive "
                "the Senior Citizen Card by post. "
                "Contact: Helpline 021-111-002-002. Email: info@sspa.gos.pk. "
                "Footer: Copyright 2026 Social Welfare Department Sindh."
            ),
            "timestamp": "2026-06-20T10:00:00Z",
            "user_id": "usr_phase1",
        },
        "expect_risk": "none",
        "expect_contains": ["senior citizen", "sindh"],
        "expect_not_contains": ["could not analyse", "scam"],
    })

    # ── Scenario 2: Investment scam WhatsApp ─────────────────────────────────
    SCENARIOS.append({
        "name": "S2  Investment scam WhatsApp",
        "endpoint": "/analyze-event",
        "payload": {
            "event_type": "SMS",
            "source_app": "com.whatsapp",
            "redacted_text": (
                "WhatsApp Group: Global Crypto Earners (145 members). "
                "Sender: +92-316-XXXXXXX (Admin). "
                "Message: Good news everyone! Our trading platform has achieved 28 percent "
                "daily returns for the 7th consecutive week. Only 13 USDT minimum to start "
                "earning passively. You can break even in just 4 days. Invite friends and "
                "earn 15 percent commission on their deposits. Join now before spots fill "
                "up. Registration link: https://cryptoearn-pk.net/invite?code=ELDER2026. "
                "Do not miss this opportunity. Limited time offer. "
                "Reply options: [Accept] [Decline] [Report Group]. "
                "Bottom bar: Camera | Gallery | Document | Audio | Location | Contact."
            ),
            "timestamp": "2026-06-20T10:01:00Z",
            "user_id": "usr_phase1",
        },
        "expect_risk": "stop_and_verify",
        "expect_contains": ["scam"],
        "expect_not_contains": ["could not analyse"],
    })

    # ── Scenario 3: Chat after failed analysis ───────────────────────────────
    SCENARIOS.append({
        "name": "S3  Chat after failed analysis",
        "endpoint": "/ask-question",
        "payload": {
            "user_id": "usr_phase1",
            "question": "Is this website authentic?",
            "screen_context": (
                "swd.sindh.gov.pk — Social Welfare Department, Government of Sindh. "
                "Sindh Senior Citizen Card — Application Form. Eligibility Criteria."
            ),
        },
        "expect_risk": "none",
        "expect_contains": [],
        "expect_not_contains": ["could not analyse"],
    })

    # ── Scenario 4: Legitimate bank login screen ─────────────────────────────
    SCENARIOS.append({
        "name": "S4  HBL bank login screen",
        "endpoint": "/analyze-event",
        "payload": {
            "event_type": "FORM_SCREEN",
            "source_app": "com.hbl.android.hblpersonal",
            "redacted_text": (
                "HBL Mobile — Habib Bank Limited. "
                "Welcome to HBL Mobile Banking. "
                "Username: [text field]. "
                "Password: [password field]. "
                "Login button. "
                "Forgot Password? Tap here to reset. "
                "Use Fingerprint to Login (toggle enabled). "
                "Security Notice: HBL will never ask you for your password, "
                "OTP, or card details via call, SMS, or email. If anyone asks, "
                "it is a scam. Report to 111-111-425. "
                "New to HBL Mobile? Register Now. "
                "Version 7.2.1. Terms and Conditions | Privacy Policy. "
                "Secured by 256-bit SSL encryption. "
                "Footer: Habib Bank Limited. A scheduled bank regulated by the "
                "State Bank of Pakistan."
            ),
            "timestamp": "2026-06-20T10:02:00Z",
            "user_id": "usr_phase1",
        },
        "expect_risk_not": "stop_and_verify",
        "expect_contains": [],
        "expect_not_contains": ["scam", "fraud"],
    })

    # ── Scenario 5: Phishing site pretending to be NADRA ─────────────────────
    SCENARIOS.append({
        "name": "S5  Phishing site fake NADRA",
        "endpoint": "/analyze-event",
        "payload": {
            "event_type": "FORM_SCREEN",
            "source_app": "com.android.chrome",
            "redacted_text": (
                "nadra-renewal-pk.com — NADRA Online CNIC Renewal Service. "
                "Logo: National Database and Registration Authority. "
                "Renew your CNIC from the comfort of your home! "
                "Enter your CNIC Number: [text field] [REDACTED_CNIC placeholder]. "
                "Date of Birth: [date picker]. "
                "Mother's Maiden Name: [text field]. "
                "Father's Name: [text field]. "
                "Processing Fee: Rs 500 (pay online to expedite your renewal). "
                "Payment Method: JazzCash | Easypaisa | Credit Card. "
                "Enter Mobile Number for OTP verification: [text field]. "
                "Submit Application button. "
                "Note: Your new CNIC will be delivered within 7 working days. "
                "Trusted by millions of Pakistanis. SSL Secured. "
                "Contact: support@nadra-renewal-pk.com. "
                "Footer: NADRA Online Services 2026. All rights reserved."
            ),
            "timestamp": "2026-06-20T10:03:00Z",
            "user_id": "usr_phase1",
        },
        "expect_risk": "stop_and_verify",
        "expect_contains": [],
        "expect_not_contains": ["could not analyse"],
    })

    # ── Scenario 6: Family emergency WhatsApp scam ───────────────────────────
    SCENARIOS.append({
        "name": "S6  Family emergency scam",
        "endpoint": "/analyze-event",
        "payload": {
            "event_type": "SMS",
            "source_app": "com.whatsapp",
            "redacted_text": (
                "WhatsApp Chat with Unknown Number +92-321-XXXXXXX. "
                "Message: Assalamualaikum Uncle ji. I am your nephew Ali. "
                "I am in Malaysia for work and I lost my phone and wallet. "
                "I am using a friend's phone to contact you. I had an accident "
                "and I am in the hospital. The hospital is asking for Rs 20000 "
                "immediately for treatment otherwise they will not treat me. "
                "Please send the money urgently to this account: "
                "JazzCash [REDACTED_PHONE]. "
                "Please do not tell anyone in the family, I do not want Ammi to worry. "
                "I will pay you back as soon as I return. Please help me Uncle ji, "
                "it is very urgent. "
                "Reply options: [Type a message] [Microphone] [Camera]."
            ),
            "timestamp": "2026-06-20T10:04:00Z",
            "user_id": "usr_phase1",
        },
        "expect_risk": "stop_and_verify",
        "expect_contains": [],
        "expect_not_contains": ["could not analyse"],
    })

    # ── Scenario 7: Pakistan Post tracking page ──────────────────────────────
    SCENARIOS.append({
        "name": "S7  Pakistan Post tracking",
        "endpoint": "/analyze-event",
        "payload": {
            "event_type": "FORM_SCREEN",
            "source_app": "com.android.chrome",
            "redacted_text": (
                "ep.gov.pk — Pakistan Post. Track and Trace. "
                "Navigation: Home | Services | Track | Contact Us. "
                "Tracking Number: CP123456789PK. "
                "Status: In Transit. "
                "Origin: Islamabad GPO, dispatched 17 June 2026. "
                "Current Location: Karachi Sorting Centre. "
                "Expected Delivery: 22 June 2026. "
                "Delivery Type: Registered Post. "
                "Weight: 0.5 kg. "
                "Tracking History: "
                "17 Jun 2026 14:30 — Accepted at Islamabad GPO. "
                "18 Jun 2026 06:15 — Dispatched from Islamabad. "
                "19 Jun 2026 22:45 — Arrived at Karachi Sorting Centre. "
                "Footer: Pakistan Post Office Department. Government of Pakistan. "
                "Helpline: 051-9202480."
            ),
            "timestamp": "2026-06-20T10:05:00Z",
            "user_id": "usr_phase1",
        },
        "expect_risk_not": "stop_and_verify",
        "expect_contains": [],
        "expect_not_contains": ["scam", "fraud"],
    })

    # ── Scenario 8: Easypaisa money transfer ─────────────────────────────────
    SCENARIOS.append({
        "name": "S8  Easypaisa money transfer",
        "endpoint": "/analyze-event",
        "payload": {
            "event_type": "FORM_SCREEN",
            "source_app": "pk.com.telenor.phoenix",
            "redacted_text": (
                "Easypaisa — Send Money. "
                "From: My Easypaisa Account (Balance: Rs 12,350). "
                "Send To: Mobile Number [REDACTED_PHONE]. "
                "Recipient Name: [REDACTED]. "
                "Amount: Rs 5,000. "
                "Transaction Fee: Rs 0 (free for Easypaisa to Easypaisa). "
                "Total: Rs 5,000. "
                "Purpose: Family Support. "
                "Review your transaction details carefully before confirming. "
                "Confirm button | Cancel button. "
                "Note: Easypaisa will never ask you to share your PIN or password. "
                "If someone is asking you to send money to claim a prize or reward, "
                "it is likely a scam. "
                "Bottom Navigation: Home | Send Money | Bill Payment | My Account."
            ),
            "timestamp": "2026-06-20T10:06:00Z",
            "user_id": "usr_phase1",
        },
        "expect_risk_not": "stop_and_verify",
        "expect_contains": [],
        "expect_not_contains": ["could not analyse"],
    })

    # ── Scenario 9: YouTube health video ─────────────────────────────────────
    SCENARIOS.append({
        "name": "S9  YouTube health video",
        "endpoint": "/analyze-event",
        "payload": {
            "event_type": "FORM_SCREEN",
            "source_app": "com.google.android.youtube",
            "redacted_text": (
                "YouTube. Channel: Dr Health Pakistan (1.2M subscribers). "
                "Video: 5 Simple Exercises for Joint Pain Relief in Seniors. "
                "Views: 245K | 2 weeks ago. "
                "Like (12K) | Dislike | Share | Save | Download. "
                "Description: In this video I explain five easy exercises that "
                "elderly people can do at home to reduce joint pain and improve "
                "mobility. No equipment needed. Always consult your doctor before "
                "starting any exercise routine. "
                "Comments (342): "
                "User1: Very helpful video, my mother tried these exercises. "
                "User2: Thank you doctor sahib, Allah bless you. "
                "Up Next: Foods That Help Joint Pain | Morning Walk Benefits."
            ),
            "timestamp": "2026-06-20T10:07:00Z",
            "user_id": "usr_phase1",
        },
        "expect_risk_not": "stop_and_verify",
        "expect_contains": [],
        "expect_not_contains": ["scam", "fraud", "dangerous"],
    })

    # ── Scenario 10: Fake prize lottery SMS ──────────────────────────────────
    SCENARIOS.append({
        "name": "S10 Fake prize lottery SMS",
        "endpoint": "/analyze-event",
        "payload": {
            "event_type": "SMS",
            "source_app": "com.android.messaging",
            "redacted_text": (
                "From: +92-300-XXXXXXX. "
                "Congratulations! You have been selected in Jazz Lucky Draw Season 14. "
                "Your mobile number has won the grand prize: "
                "1x Apple iPhone 15 Pro Max (256GB) and Rs 100,000 cash. "
                "To claim your prize, call our prize distribution centre at "
                "[REDACTED_PHONE] within 24 hours. "
                "You will need to provide your CNIC number and pay a processing "
                "fee of Rs 2,500 via Easypaisa or JazzCash to receive your prize. "
                "This is a limited time offer. Do not share this message with anyone "
                "or your prize will be cancelled. "
                "Reference Number: JLD-2026-78432. "
                "Jazz Telecommunications — Official Lucky Draw Committee."
            ),
            "timestamp": "2026-06-20T10:08:00Z",
            "user_id": "usr_phase1",
        },
        "expect_risk": "stop_and_verify",
        "expect_contains": [],
        "expect_not_contains": ["could not analyse"],
    })

    # ── Run all scenarios ────────────────────────────────────────────────────
    results = []
    _response_cache.clear()

    for i, sc in enumerate(SCENARIOS, 1):
        _response_cache.clear()
        t0 = time.perf_counter()
        resp = client.post(sc["endpoint"], json=sc["payload"])
        latency_ms = (time.perf_counter() - t0) * 1000
        body = resp.json()

        status = resp.status_code
        risk = body.get("risk_flag", "N/A")
        text = body.get("response_text", "")
        steps = body.get("next_steps", [])

        # Determine pass/fail
        passed = True
        fail_reasons = []

        if status != 200:
            passed = False
            fail_reasons.append(f"HTTP {status}")

        if "expect_risk" in sc and risk != sc["expect_risk"]:
            passed = False
            fail_reasons.append(f"risk={risk}, expected {sc['expect_risk']}")

        if "expect_risk_not" in sc and risk == sc["expect_risk_not"]:
            passed = False
            fail_reasons.append(f"risk={risk}, must NOT be {sc['expect_risk_not']}")

        for word in sc.get("expect_contains", []):
            if word.lower() not in text.lower():
                passed = False
                fail_reasons.append(f"missing '{word}'")

        for word in sc.get("expect_not_contains", []):
            if word.lower() in text.lower():
                passed = False
                fail_reasons.append(f"contains forbidden '{word}'")

        results.append({
            "name": sc["name"],
            "status": status,
            "risk": risk,
            "text": text,
            "steps": steps,
            "latency_ms": latency_ms,
            "passed": passed,
            "fail_reasons": fail_reasons,
            "sent_preview": (sc["payload"].get("redacted_text") or sc["payload"].get("question", ""))[:200],
        })

    # ── Print detailed results ───────────────────────────────────────────────
    print("\n" + "=" * 100)
    print("PHASE 1 -- DEEP LOCAL TESTING -- 10 SCENARIOS (BEFORE UPGRADE)")
    print("=" * 100)

    for r in results:
        verdict = "PASS" if r["passed"] else f"FAIL ({'; '.join(r['fail_reasons'])})"
        print(f"\n{'-' * 100}")
        print(f"  {r['name']}  [{verdict}]  {r['latency_ms']:.0f}ms")
        print(f"{'-' * 100}")
        print(f"  Sent:          {r['sent_preview']}...")
        print(f"  HTTP:          {r['status']}")
        print(f"  risk_flag:     {r['risk']}")
        print(f"  response_text: {r['text']}")
        print(f"  next_steps:    {r['steps']}")

    # ── Summary table ────────────────────────────────────────────────────────
    print(f"\n{'=' * 100}")
    print(f"{'Scenario':<42} {'Status':<6} {'Risk':<20} {'Latency':<10} {'Result'}")
    print(f"{'=' * 100}")
    pass_count = 0
    for r in results:
        verdict = "PASS" if r["passed"] else "FAIL"
        if r["passed"]:
            pass_count += 1
        print(f"{r['name']:<42} {r['status']:<6} {r['risk']:<20} {r['latency_ms']:>6.0f}ms   {verdict}")
    print(f"{'=' * 100}")
    print(f"Total: {pass_count}/{len(results)} passed")
