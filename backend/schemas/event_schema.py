from enum import Enum
from datetime import datetime
from typing import Union

from pydantic import BaseModel, Field, field_validator


class EventType(str, Enum):
    SMS = "SMS"
    FORM_SCREEN = "FORM_SCREEN"
    DOCUMENT = "DOCUMENT"
    NOTIFICATION = "NOTIFICATION"
    CALL_CONTEXT = "CALL_CONTEXT"
    PAYMENT_CONTEXT = "PAYMENT_CONTEXT"
    UNKNOWN = "UNKNOWN"


class IncomingEvent(BaseModel):
    event_type: EventType = Field(
        ...,
        description="Category of the captured event from the device layer.",
    )
    source_app: str = Field(
        ...,
        description="Package name or label of the app that triggered the event (e.g. 'com.whatsapp', 'SMS', 'Chrome').",
        min_length=1,
        max_length=128,
    )
    redacted_text: str = Field(
        ...,
        description=(
            "Accessible text of the screen, notification body, or document excerpt "
            "after local PII/OTP redaction. Never contains raw OTPs, CNICs, "
            "passwords, or bank numbers."
        ),
        max_length=4096,
    )
    timestamp: Union[datetime, str] = Field(
        ...,
        description="ISO-8601 UTC timestamp of when the event was captured on-device.",
    )

    @field_validator("timestamp", mode="before")
    @classmethod
    def parse_timestamp(cls, v: object) -> datetime:
        if isinstance(v, datetime):
            return v
        try:
            return datetime.fromisoformat(str(v).replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError(f"Invalid timestamp format: {v!r}") from exc
    user_id: str = Field(
        ...,
        description="Opaque, non-reversible identifier for the user. Never a name or contact value.",
        min_length=1,
        max_length=64,
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "event_type": "NOTIFICATION",
                "source_app": "com.android.messaging",
                "redacted_text": "Govt health grant approved. Enter [REDACTED_CNIC] at senior-help.info",
                "timestamp": "2026-06-15T14:30:00Z",
                "user_id": "usr_a1b2c3d4e5f6",
            }
        }
    }
