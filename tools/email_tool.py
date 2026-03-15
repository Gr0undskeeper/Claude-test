"""
Microsoft Graph API — Outlook email integration.
Uses MSAL device-code flow for authentication (no browser required on first run).
Tools: read_emails, send_email, search_emails
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import config

# OAuth2 scopes needed
_SCOPES = ["Mail.Read", "Mail.Send", "User.Read"]
_GRAPH_BASE = "https://graph.microsoft.com/v1.0"

# Tool schemas ─────────────────────────────────────────────────────────────────

TOOL_READ_EMAILS = {
    "name": "read_emails",
    "description": (
        "Read emails from the Outlook inbox (or another folder). "
        "Returns subject, sender, date, and body preview."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "folder": {
                "type": "string",
                "description": "Mailbox folder name (default: inbox).",
                "default": "inbox",
            },
            "limit": {
                "type": "integer",
                "description": "Max number of emails to return (default 10).",
                "default": 10,
            },
            "unread_only": {
                "type": "boolean",
                "description": "If true, return only unread emails.",
                "default": False,
            },
        },
        "required": [],
    },
}

TOOL_SEND_EMAIL = {
    "name": "send_email",
    "description": "Send an email via Outlook.",
    "input_schema": {
        "type": "object",
        "properties": {
            "to": {
                "type": "string",
                "description": "Recipient email address.",
            },
            "subject": {"type": "string", "description": "Email subject line."},
            "body": {
                "type": "string",
                "description": "Email body (plain text or basic HTML).",
            },
            "cc": {
                "type": "string",
                "description": "CC email address (optional).",
            },
        },
        "required": ["to", "subject", "body"],
    },
}

TOOL_SEARCH_EMAILS = {
    "name": "search_emails",
    "description": "Search emails by keyword in subject or body.",
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Search query string.",
            },
            "limit": {
                "type": "integer",
                "description": "Max results (default 10).",
                "default": 10,
            },
        },
        "required": ["query"],
    },
}

EMAIL_TOOLS = [TOOL_READ_EMAILS, TOOL_SEND_EMAIL, TOOL_SEARCH_EMAILS]

# Auth ─────────────────────────────────────────────────────────────────────────


def _get_token() -> str:
    if not config.EMAIL_ENABLED:
        raise RuntimeError(
            "Email is not configured. Set AZURE_CLIENT_ID in your .env file."
        )
    import msal  # type: ignore

    cache_path = Path(config.MSAL_TOKEN_CACHE)
    cache = msal.SerializableTokenCache()
    if cache_path.exists():
        cache.deserialize(cache_path.read_text())

    app = msal.PublicClientApplication(
        config.AZURE_CLIENT_ID,
        authority=f"https://login.microsoftonline.com/{config.AZURE_TENANT_ID}",
        token_cache=cache,
    )

    accounts = app.get_accounts()
    result = None
    if accounts:
        result = app.acquire_token_silent(_SCOPES, account=accounts[0])

    if not result:
        flow = app.initiate_device_flow(scopes=_SCOPES)
        print(f"\n[Auth] {flow['message']}\n")
        result = app.acquire_token_by_device_flow(flow)

    # Persist token cache
    if cache.has_state_changed:
        cache_path.write_text(cache.serialize())

    if "access_token" not in result:
        raise RuntimeError(f"MSAL auth failed: {result.get('error_description')}")

    return result["access_token"]


def _graph(method: str, path: str, **kwargs) -> Any:
    import requests  # type: ignore

    token = _get_token()
    url = f"{_GRAPH_BASE}{path}"
    resp = requests.request(
        method,
        url,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        **kwargs,
    )
    resp.raise_for_status()
    if resp.content:
        return resp.json()
    return {}


# Executors ────────────────────────────────────────────────────────────────────


def read_emails(folder: str = "inbox", limit: int = 10, unread_only: bool = False) -> list[dict]:
    params: dict[str, Any] = {
        "$top": limit,
        "$orderby": "receivedDateTime desc",
        "$select": "subject,from,receivedDateTime,bodyPreview,isRead",
    }
    if unread_only:
        params["$filter"] = "isRead eq false"

    data = _graph("GET", f"/me/mailFolders/{folder}/messages", params=params)
    emails = []
    for m in data.get("value", []):
        emails.append(
            {
                "subject": m.get("subject"),
                "from": m.get("from", {}).get("emailAddress", {}).get("address"),
                "received": m.get("receivedDateTime"),
                "preview": m.get("bodyPreview"),
                "is_read": m.get("isRead"),
            }
        )
    return emails


def send_email(to: str, subject: str, body: str, cc: str = "") -> dict:
    payload: dict[str, Any] = {
        "message": {
            "subject": subject,
            "body": {"contentType": "Text", "content": body},
            "toRecipients": [{"emailAddress": {"address": to}}],
        }
    }
    if cc:
        payload["message"]["ccRecipients"] = [{"emailAddress": {"address": cc}}]

    _graph("POST", "/me/sendMail", json=payload)
    return {"status": "sent", "to": to, "subject": subject}


def search_emails(query: str, limit: int = 10) -> list[dict]:
    params = {
        "$search": f'"{query}"',
        "$top": limit,
        "$select": "subject,from,receivedDateTime,bodyPreview",
    }
    data = _graph("GET", "/me/messages", params=params,
                  headers={"ConsistencyLevel": "eventual",
                           "Authorization": f"Bearer {_get_token()}",
                           "Content-Type": "application/json"})
    results = []
    for m in data.get("value", []):
        results.append(
            {
                "subject": m.get("subject"),
                "from": m.get("from", {}).get("emailAddress", {}).get("address"),
                "received": m.get("receivedDateTime"),
                "preview": m.get("bodyPreview"),
            }
        )
    return results


def execute(tool_name: str, tool_input: dict[str, Any]) -> Any:
    if tool_name == "read_emails":
        return read_emails(**tool_input)
    if tool_name == "send_email":
        return send_email(**tool_input)
    if tool_name == "search_emails":
        return search_emails(**tool_input)
    raise ValueError(f"Unknown email tool: {tool_name}")
