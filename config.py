"""
Configuration — loads all environment variables and exposes them as typed constants.
Copy .env.example to .env and fill in your credentials.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")


def _require(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise EnvironmentError(
            f"Missing required environment variable: {name}\n"
            f"See .env.example for setup instructions."
        )
    return value


def _optional(name: str, default: str = "") -> str:
    return os.getenv(name, default)


# ── Anthropic ─────────────────────────────────────────────────────────────────
ANTHROPIC_API_KEY: str = _require("ANTHROPIC_API_KEY")
CLAUDE_MODEL: str = _optional("CLAUDE_MODEL", "claude-sonnet-4-6")

# ── Twilio SMS ────────────────────────────────────────────────────────────────
TWILIO_ACCOUNT_SID: str = _optional("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN: str = _optional("TWILIO_AUTH_TOKEN")
TWILIO_PHONE_NUMBER: str = _optional("TWILIO_PHONE_NUMBER")  # E.164 format: +1234567890

# ── Microsoft Graph (Outlook) ─────────────────────────────────────────────────
AZURE_CLIENT_ID: str = _optional("AZURE_CLIENT_ID")
AZURE_TENANT_ID: str = _optional("AZURE_TENANT_ID", "common")
# Token cache file for persisting MSAL tokens between runs
MSAL_TOKEN_CACHE: str = _optional("MSAL_TOKEN_CACHE", ".msal_token_cache.json")

# ── Google Calendar ───────────────────────────────────────────────────────────
GOOGLE_CREDENTIALS_FILE: str = _optional("GOOGLE_CREDENTIALS_FILE", "google_credentials.json")
GOOGLE_TOKEN_FILE: str = _optional("GOOGLE_TOKEN_FILE", ".google_token.json")
GOOGLE_CALENDAR_ID: str = _optional("GOOGLE_CALENDAR_ID", "primary")

# ── Feature flags (set to "false" to disable an integration) ─────────────────
SMS_ENABLED: bool = all([TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_PHONE_NUMBER])
EMAIL_ENABLED: bool = all([AZURE_CLIENT_ID])
CALENDAR_ENABLED: bool = bool(GOOGLE_CREDENTIALS_FILE)
