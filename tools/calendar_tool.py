"""
Google Calendar API integration.
Uses OAuth2 with a local credentials file (Desktop app flow).
Tools: get_events, create_event, delete_event
"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

import config

_SCOPES = ["https://www.googleapis.com/auth/calendar"]

# Tool schemas ─────────────────────────────────────────────────────────────────

TOOL_GET_EVENTS = {
    "name": "get_events",
    "description": (
        "Retrieve upcoming events from Google Calendar. "
        "Returns event title, start/end time, location, and description."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "days_ahead": {
                "type": "integer",
                "description": "How many days ahead to look (default 7).",
                "default": 7,
            },
            "max_results": {
                "type": "integer",
                "description": "Maximum number of events to return (default 20).",
                "default": 20,
            },
        },
        "required": [],
    },
}

TOOL_CREATE_EVENT = {
    "name": "create_event",
    "description": "Create a new event on Google Calendar.",
    "input_schema": {
        "type": "object",
        "properties": {
            "title": {"type": "string", "description": "Event title / summary."},
            "start": {
                "type": "string",
                "description": "Start datetime in ISO 8601 format (e.g. 2026-03-20T14:00:00).",
            },
            "end": {
                "type": "string",
                "description": "End datetime in ISO 8601 format.",
            },
            "description": {
                "type": "string",
                "description": "Optional event description / notes.",
            },
            "location": {
                "type": "string",
                "description": "Optional event location.",
            },
            "attendees": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Optional list of attendee email addresses.",
            },
        },
        "required": ["title", "start", "end"],
    },
}

TOOL_DELETE_EVENT = {
    "name": "delete_event",
    "description": "Delete a calendar event by its event ID.",
    "input_schema": {
        "type": "object",
        "properties": {
            "event_id": {
                "type": "string",
                "description": "The Google Calendar event ID to delete.",
            }
        },
        "required": ["event_id"],
    },
}

CALENDAR_TOOLS = [TOOL_GET_EVENTS, TOOL_CREATE_EVENT, TOOL_DELETE_EVENT]

# Auth ─────────────────────────────────────────────────────────────────────────


def _get_service():
    if not config.CALENDAR_ENABLED:
        raise RuntimeError(
            "Google Calendar is not configured. Set GOOGLE_CREDENTIALS_FILE in your .env file."
        )
    from google.oauth2.credentials import Credentials  # type: ignore
    from google_auth_oauthlib.flow import InstalledAppFlow  # type: ignore
    from google.auth.transport.requests import Request  # type: ignore
    from googleapiclient.discovery import build  # type: ignore

    token_path = Path(config.GOOGLE_TOKEN_FILE)
    creds = None

    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), _SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                config.GOOGLE_CREDENTIALS_FILE, _SCOPES
            )
            creds = flow.run_local_server(port=0)
        token_path.write_text(creds.to_json())

    return build("calendar", "v3", credentials=creds)


# Executors ────────────────────────────────────────────────────────────────────


def get_events(days_ahead: int = 7, max_results: int = 20) -> list[dict]:
    service = _get_service()
    now = datetime.now(timezone.utc)
    time_max = now + timedelta(days=days_ahead)

    result = (
        service.events()
        .list(
            calendarId=config.GOOGLE_CALENDAR_ID,
            timeMin=now.isoformat(),
            timeMax=time_max.isoformat(),
            maxResults=max_results,
            singleEvents=True,
            orderBy="startTime",
        )
        .execute()
    )

    events = []
    for e in result.get("items", []):
        start = e["start"].get("dateTime", e["start"].get("date"))
        end = e["end"].get("dateTime", e["end"].get("date"))
        events.append(
            {
                "id": e.get("id"),
                "title": e.get("summary"),
                "start": start,
                "end": end,
                "location": e.get("location"),
                "description": e.get("description"),
                "attendees": [
                    a.get("email") for a in e.get("attendees", [])
                ],
            }
        )
    return events


def create_event(
    title: str,
    start: str,
    end: str,
    description: str = "",
    location: str = "",
    attendees: list[str] | None = None,
) -> dict:
    service = _get_service()

    body: dict[str, Any] = {
        "summary": title,
        "start": {"dateTime": start, "timeZone": "UTC"},
        "end": {"dateTime": end, "timeZone": "UTC"},
    }
    if description:
        body["description"] = description
    if location:
        body["location"] = location
    if attendees:
        body["attendees"] = [{"email": a} for a in attendees]

    event = (
        service.events()
        .insert(calendarId=config.GOOGLE_CALENDAR_ID, body=body)
        .execute()
    )
    return {
        "status": "created",
        "id": event.get("id"),
        "title": title,
        "start": start,
        "end": end,
        "link": event.get("htmlLink"),
    }


def delete_event(event_id: str) -> dict:
    service = _get_service()
    service.events().delete(
        calendarId=config.GOOGLE_CALENDAR_ID, eventId=event_id
    ).execute()
    return {"status": "deleted", "event_id": event_id}


def execute(tool_name: str, tool_input: dict[str, Any]) -> Any:
    if tool_name == "get_events":
        return get_events(**tool_input)
    if tool_name == "create_event":
        return create_event(**tool_input)
    if tool_name == "delete_event":
        return delete_event(**tool_input)
    raise ValueError(f"Unknown calendar tool: {tool_name}")
