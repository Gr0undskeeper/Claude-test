"""
Twilio SMS integration.
Tools: send_sms, get_recent_sms
"""
from __future__ import annotations

from typing import Any

import config

# Tool schemas for the Anthropic SDK ──────────────────────────────────────────

TOOL_SEND_SMS = {
    "name": "send_sms",
    "description": "Send an SMS message to a phone number via Twilio.",
    "input_schema": {
        "type": "object",
        "properties": {
            "to": {
                "type": "string",
                "description": "Recipient phone number in E.164 format (e.g. +14155552671)",
            },
            "body": {
                "type": "string",
                "description": "The text content of the SMS message.",
            },
        },
        "required": ["to", "body"],
    },
}

TOOL_GET_RECENT_SMS = {
    "name": "get_recent_sms",
    "description": (
        "Retrieve recent SMS messages from the Twilio account log. "
        "Returns both sent and received messages."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "limit": {
                "type": "integer",
                "description": "Maximum number of messages to retrieve (default 10).",
                "default": 10,
            },
            "direction": {
                "type": "string",
                "enum": ["all", "inbound", "outbound-api"],
                "description": "Filter by message direction (default: all).",
                "default": "all",
            },
        },
        "required": [],
    },
}

SMS_TOOLS = [TOOL_SEND_SMS, TOOL_GET_RECENT_SMS]

# Executor ────────────────────────────────────────────────────────────────────


def _client():
    if not config.SMS_ENABLED:
        raise RuntimeError(
            "SMS is not configured. Set TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, "
            "and TWILIO_PHONE_NUMBER in your .env file."
        )
    from twilio.rest import Client  # type: ignore
    return Client(config.TWILIO_ACCOUNT_SID, config.TWILIO_AUTH_TOKEN)


def send_sms(to: str, body: str) -> dict[str, Any]:
    client = _client()
    message = client.messages.create(
        body=body,
        from_=config.TWILIO_PHONE_NUMBER,
        to=to,
    )
    return {
        "status": "sent",
        "sid": message.sid,
        "to": to,
        "body": body,
    }


def get_recent_sms(limit: int = 10, direction: str = "all") -> list[dict[str, Any]]:
    client = _client()
    kwargs: dict[str, Any] = {"limit": limit}
    if direction != "all":
        kwargs["direction"] = direction

    messages = client.messages.list(**kwargs)
    result = []
    for m in messages:
        result.append(
            {
                "sid": m.sid,
                "from": m.from_,
                "to": m.to,
                "body": m.body,
                "direction": m.direction,
                "status": m.status,
                "date_sent": str(m.date_sent),
            }
        )
    return result


def execute(tool_name: str, tool_input: dict[str, Any]) -> Any:
    if tool_name == "send_sms":
        return send_sms(**tool_input)
    if tool_name == "get_recent_sms":
        return get_recent_sms(**tool_input)
    raise ValueError(f"Unknown SMS tool: {tool_name}")
