"""
Router Agent — dynamic dispatcher for the ElderBridge trust engine.

Responsibility (AI_AGENTS.md §4):
  Receives a normalised IncomingEvent and decides which specialist agents
  should be activated for this particular event, avoiding the cost and
  context pollution of running every agent on every event.

Pipeline contract (ARCHITECTURE.md §6):
  Router runs first, before critic and guardrail.  It returns ONLY the
  specialist agents; CriticAgent and GuardrailAgent are always appended by
  the orchestrator and must NOT appear in route() output.

Signal-aware routing rules:
  Any event type:
    + benefit/grant/pension keywords  → also add BenefitsAgent
    + url/link/domain keywords        → also add ResearchAgent

  Base routing by event type:
    SMS / NOTIFICATION  → ResearchAgent           (scam/link verification)
    FORM_SCREEN         → FormAgent, BenefitsAgent
    DOCUMENT            → FormAgent, BenefitsAgent, ResearchAgent
"""
from __future__ import annotations

from typing import List

from schemas.decision_schema import AgentResponse
from schemas.event_schema import EventType, IncomingEvent

# ---------------------------------------------------------------------------
# Keyword-based secondary routing signals
# ---------------------------------------------------------------------------

_BENEFIT_SIGNALS = [
    "benefit", "grant", "pension", "healthcare", "welfare",
    "allowance", "subsidy", "support program", "eligib",
]

_RESEARCH_SIGNALS = [
    "http", ".com", ".org", ".info", ".net", "link", "website",
    "click", "tap here", "verify", "official", "government",
]

_SCAM_ESCALATION_SIGNALS = [
    "otp", "[redacted_otp]", "password", "cnic", "[redacted_cnic]",
    "transfer", "send money", "urgent", "immediately", "expire",
    "suspended", "blocked", "arrest", "threat",
    # Prize/lottery scams
    "won", "prize", "lucky draw", "lottery", "congratulations",
    # Telecom scams
    "recharge", "sim block", "network upgrade", "verify sim",
    # Job scams
    "job offer", "earn from home", "part time", "online work",
    # Delivery scams
    "parcel", "package", "courier", "customs", "held",
    # Bank scams
    "account block", "kyc update", "verify account", "atm blocked",
    # Romanized Urdu scam patterns
    "mubarak", "inaam", "inam", "khata",
]

# ---------------------------------------------------------------------------
# Low-signal screen detection — screens with no actionable content
# ---------------------------------------------------------------------------

_LOW_SIGNAL_APPS = [
    "launcher", "nexuslauncher", "settings", "documentsui",
    "filemanager", "deskclock", "calculator", "wallpaper",
]

_MEDIA_APPS = [
    "youtube", "netflix", "spotify", "tiktok", "dailymotion",
    "vlc", "mx.player", "video", "music", "gallery", "photos",
    "camera", "instagram.android",
    "com.facebook.katana", "com.twitter.android", "com.tiktok.android",
    "com.google.android.apps.maps", "com.weather.app",
    "com.google.android.apps.photos",
    "com.discord", "org.telegram.messenger", "com.snapchat.android",
    "com.reddit.frontpage", "com.linkedin.android",
    "com.google.android.youtube",
]

_BANKING_APPS = [
    "com.hbl.", "pk.com.telenor.phoenix", "com.jazzcash", "com.mobilink",
    "com.mcb.", "com.ubl.", "com.standardchartered.", "com.faysal.",
    "com.askari.", "com.alfalah.", "com.meezanbank.", "com.bankislami.",
    "pk.com.ubldigital", "com.js.bank", "com.nayapay.", "com.sadapay.",
    "com.meezan.bank", "com.ubldigital.umobile", "com.faysal.bank",
    "com.bankalfalah.mobile", "com.mcb.mcbmobilebanking", "com.abl.digitalabl",
    "com.jazzcash.android",
]

_FINANCIAL_TRANSACTION_APPS = [
    "pk.com.telenor.phoenix", "com.jazzcash", "com.mobilink",
    "com.nayapay.", "com.sadapay.",
]

_ACTIONABLE_CONTENT = [
    "form", "apply", "enter", "submit", "payment", "transfer",
    "otp", "password", "benefit", "pension", "message", "notice",
    "bill", "statement", "document", "letter", "application",
    "registration", "enrollment", "eligible", "cnic", "nadra",
    "ehsaas", "bisp", "grant", "healthcare", "amount", "rupee",
    "pkr", "bank", "account", "verify", "claim", "approve",
    "income", "household", "dependent", "upload", "download",
    "scam", "fraud", "prize", "lottery", "congratulations",
    "urgent", "expire", "blocked", "suspended",
]

_LOW_SIGNAL_KEYWORDS = [
    "home screen", "app drawer", "recent apps",
    "file manager", "my files", "internal storage",
    "downloads folder", "no new notification",
]


def _is_low_signal(text: str, source_app: str) -> bool:
    """Return True if the screen has no actionable content worth analysing."""
    text_lower = text.lower().strip()
    source_lower = source_app.lower()

    if len(text_lower) < 20:
        return True

    if any(kw in text_lower for kw in _LOW_SIGNAL_KEYWORDS):
        return True

    if any(app in source_lower for app in _LOW_SIGNAL_APPS):
        if not any(a in text_lower for a in _ACTIONABLE_CONTENT):
            return True

    if any(app in source_lower for app in _MEDIA_APPS):
        if not any(a in text_lower for a in _ACTIONABLE_CONTENT):
            return True

    return False


def classify_context(event: IncomingEvent) -> str:
    """Classify the screen into a context type for agent routing decisions.

    Returns one of: banking_app, government_form, media_content,
    financial_transaction, legitimate_message, low_signal, or default.
    """
    source_lower = event.source_app.lower()
    text_lower = event.redacted_text.lower()

    if _is_low_signal(event.redacted_text, event.source_app):
        return "low_signal"

    if any(app in source_lower for app in _MEDIA_APPS):
        return "media_content"

    if any(pkg in source_lower for pkg in _BANKING_APPS):
        return "banking_app"

    if any(pkg in source_lower for pkg in _FINANCIAL_TRANSACTION_APPS):
        if any(w in text_lower for w in ["send", "transfer", "pay", "amount"]):
            return "financial_transaction"
        return "banking_app"

    if ".gov." in text_lower or any(w in text_lower for w in ["nadra", "bisp", "ehsaas", "government"]):
        return "government_form"

    if event.event_type in (EventType.SMS, EventType.NOTIFICATION):
        return "legitimate_message"

    return "default"


class RouterAgent:
    """Decides which specialist agents to invoke for a given event."""

    NAME = "RouterAgent"

    # Base specialist agents by event type (critic + guardrail added by orchestrator).
    # FORM_SCREEN routes to FormAgent only; BenefitsAgent is added by secondary routing
    # when benefit-related keywords (pension, healthcare, grant, etc.) are detected.
    # This prevents the benefits agent from treating plain CNIC/income fields as scams.
    _BASE_ROUTING: dict[EventType, List[str]] = {
        EventType.SMS: ["ResearchAgent"],
        EventType.NOTIFICATION: ["ResearchAgent"],
        EventType.FORM_SCREEN: ["FormAgent"],
        EventType.DOCUMENT: ["FormAgent", "BenefitsAgent", "ResearchAgent"],
    }

    def route(self, event: IncomingEvent) -> List[str]:
        """
        Return the ordered list of specialist agent names to invoke.

        CriticAgent and GuardrailAgent are NOT included here; the orchestrator
        always appends them at the end of the pipeline.

        Signal-aware secondary routing adds agents based on keywords found
        in the event's redacted text, regardless of event type.

        Low-signal screens (home screen, app drawer, file manager, settings)
        return an empty list so no specialist agents run.

        Args:
            event: Normalised, redacted event from the device layer.

        Returns:
            Ordered list of specialist agent name strings.
        """
        if _is_low_signal(event.redacted_text, event.source_app):
            return []

        agents: list[str] = list(self._BASE_ROUTING.get(event.event_type, ["ResearchAgent"]))
        text_lower = event.redacted_text.lower()

        # Add BenefitsAgent if benefit-related content is found and not already listed
        if "BenefitsAgent" not in agents:
            if any(sig in text_lower for sig in _BENEFIT_SIGNALS):
                agents.append("BenefitsAgent")

        # Add ResearchAgent if URLs/links are found and not already listed
        if "ResearchAgent" not in agents:
            if any(sig in text_lower for sig in _RESEARCH_SIGNALS):
                agents.append("ResearchAgent")

        # Escalate to include ResearchAgent for high-risk scam signals on SMS/NOTIFICATION
        if event.event_type in (EventType.SMS, EventType.NOTIFICATION):
            if any(sig in text_lower for sig in _SCAM_ESCALATION_SIGNALS):
                if "BenefitsAgent" not in agents:
                    agents.append("BenefitsAgent")

        return agents

    def run(self, event: IncomingEvent) -> AgentResponse:
        """
        Convenience wrapper: runs route() and packages the result as an AgentResponse.

        The orchestrator calls route() directly for the agent list; this method
        exists so RouterAgent conforms to the same run() interface as all other agents
        and can be logged uniformly.

        Args:
            event: Normalised, redacted event from the device layer.

        Returns:
            AgentResponse whose output_text lists the chosen specialist agents.
        """
        agents_to_run = self.route(event)
        return AgentResponse(
            agent_name=self.NAME,
            output_text=f"Routing to specialists: {', '.join(agents_to_run)}",
            confidence=1.0,
            sources=[],
            requires_human_review=False,
        )
