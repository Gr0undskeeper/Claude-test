"""
Chief of Staff — the main orchestrator agent.
Has access to all integration tools plus the ability to:
  - Spin up specialist sub-agents (delegate_to_specialist)
  - Save key facts to shared memory (save_fact)
"""
from __future__ import annotations

import json
from typing import Any

from agents.base_agent import BaseAgent
from agents.specialist import SpecialistAgent
from memory.store import MemoryStore
from tools import calendar_tool, email_tool, sms_tool
import config

# ── Additional tools only the Chief of Staff has ──────────────────────────────

TOOL_DELEGATE = {
    "name": "delegate_to_specialist",
    "description": (
        "Spin up a specialist sub-agent with deep domain expertise. "
        "Use this when a task requires deep knowledge in a specific field "
        "(finance, travel, health, legal, research, scheduling, writing, technical). "
        "The specialist will have access to email, calendar, and SMS. "
        "It will return a detailed result which you can then summarize for the user."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "specialist_type": {
                "type": "string",
                "enum": [
                    "finance", "travel", "health", "legal",
                    "research", "scheduling", "writing", "technical"
                ],
                "description": "The domain expertise needed.",
            },
            "task": {
                "type": "string",
                "description": (
                    "Full, self-contained description of the task for the specialist. "
                    "Include all relevant details — the specialist has no prior conversation context."
                ),
            },
            "context": {
                "type": "string",
                "description": "Any extra context or constraints for the specialist.",
            },
        },
        "required": ["specialist_type", "task"],
    },
}

TOOL_SAVE_FACT = {
    "name": "save_fact",
    "description": (
        "Save an important fact about the user to shared memory. "
        "Use this whenever you learn something persistent and useful: preferences, "
        "contacts, routines, goals, constraints, or other key personal details."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "category": {
                "type": "string",
                "description": "Category for the fact (e.g. preference, contact, routine, goal, constraint).",
            },
            "key": {
                "type": "string",
                "description": "Short identifier for the fact (e.g. 'preferred_airline').",
            },
            "value": {
                "type": "string",
                "description": "The fact value (e.g. 'Delta, always window seat').",
            },
        },
        "required": ["category", "key", "value"],
    },
}

# ── Chief of Staff agent ───────────────────────────────────────────────────────

_CHIEF_SYSTEM = """You are an elite personal Chief of Staff — a trusted, highly capable executive \
assistant with broad knowledge and exceptional judgment.

Your role:
- Manage the user's communications (SMS, email) and calendar on their behalf
- Proactively surface important information (unread emails, upcoming events, etc.)
- Handle routine requests directly using your tools
- Delegate complex, domain-specific tasks to the appropriate specialist agent
- Learn and remember the user's preferences, contacts, and patterns over time

Decision framework — when to delegate vs. handle directly:
- Handle directly: scheduling questions, reading/sending messages, calendar lookups, \
simple summaries, quick answers
- Delegate to specialist: financial analysis, travel planning, legal interpretation, \
health guidance, technical deep-dives, long-form writing, in-depth research

Always be concise, proactive, and professional. Anticipate needs. \
If you don't have enough information to act, ask one focused clarifying question."""


class ChiefOfStaffAgent(BaseAgent):
    name = "chief_of_staff"

    def __init__(self, memory: MemoryStore):
        super().__init__(memory)
        self.tools = self._build_tools()

    @property
    def system_prompt(self) -> str:
        return _CHIEF_SYSTEM

    def _build_tools(self) -> list[dict]:
        tools = [TOOL_DELEGATE, TOOL_SAVE_FACT]
        if config.SMS_ENABLED:
            tools.extend(sms_tool.SMS_TOOLS)
        if config.EMAIL_ENABLED:
            tools.extend(email_tool.EMAIL_TOOLS)
        if config.CALENDAR_ENABLED:
            tools.extend(calendar_tool.CALENDAR_TOOLS)
        return tools

    def _execute_tool(self, tool_name: str, tool_input: dict[str, Any]) -> Any:
        if tool_name == "delegate_to_specialist":
            return self._delegate(tool_input)
        if tool_name == "save_fact":
            return self._save_fact(tool_input)
        if tool_name in ("send_sms", "get_recent_sms"):
            return sms_tool.execute(tool_name, tool_input)
        if tool_name in ("read_emails", "send_email", "search_emails"):
            return email_tool.execute(tool_name, tool_input)
        if tool_name in ("get_events", "create_event", "delete_event"):
            return calendar_tool.execute(tool_name, tool_input)
        raise ValueError(f"Unknown tool: {tool_name}")

    def _delegate(self, tool_input: dict[str, Any]) -> str:
        specialist_type = tool_input["specialist_type"]
        task = tool_input["task"]
        context = tool_input.get("context", "")

        print(f"\n  [Delegating to {specialist_type} specialist...]\n")

        specialist = SpecialistAgent(
            specialist_type=specialist_type,
            task=task,
            context=context,
            memory=self.memory,
        )
        result = specialist.run_and_save()
        return f"[{specialist_type.upper()} SPECIALIST REPORT]\n{result}"

    def _save_fact(self, tool_input: dict[str, Any]) -> dict:
        self.memory.add_fact(
            category=tool_input["category"],
            key=tool_input["key"],
            value=tool_input["value"],
        )
        return {"status": "saved", **tool_input}
