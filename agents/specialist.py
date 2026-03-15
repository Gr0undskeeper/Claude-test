"""
Specialist agent factory.
The Chief of Staff spins up a SpecialistAgent when deep domain expertise is needed.
Each specialist type has a focused system prompt and access to all integration tools.
"""
from __future__ import annotations

from typing import Any

from agents.base_agent import BaseAgent
from memory.store import MemoryStore
from tools import calendar_tool, email_tool, sms_tool
import config

# ── System prompts per specialist type ────────────────────────────────────────

_SYSTEM_PROMPTS: dict[str, str] = {
    "finance": """You are a world-class Chief Financial Officer and personal finance expert.
You help with budgeting, investment analysis, expense tracking, financial planning, tax strategy,
and interpreting financial data. Be precise with numbers. Provide actionable recommendations.
You have access to the user's email and calendar to find financial information.""",

    "travel": """You are an expert personal travel concierge with decades of experience.
You excel at itinerary planning, flight/hotel recommendations, visa requirements, packing lists,
local tips, and logistics optimization. Consider the user's calendar for scheduling.
You have access to the user's email and calendar.""",

    "health": """You are a knowledgeable health and wellness advisor.
You help interpret health-related information, suggest lifestyle improvements, track habits,
remind about appointments, and provide general wellness guidance (not medical advice).
Always recommend consulting a qualified professional for medical decisions.
You have access to the user's calendar for appointment tracking.""",

    "legal": """You are a highly knowledgeable legal research assistant.
You help understand legal concepts, summarize contracts, flag potential issues,
and research legal topics. Always clarify that you provide information, not legal advice,
and recommend consulting a licensed attorney for binding decisions.""",

    "research": """You are a rigorous research analyst and investigator.
You excel at synthesizing information, fact-checking, competitive analysis,
summarizing complex topics, and presenting findings clearly.
Use the user's email and calendar context when relevant.""",

    "scheduling": """You are a master scheduler and time management expert.
You optimize calendars, resolve scheduling conflicts, draft meeting invitations,
manage time zones, and ensure the user's schedule is efficient and balanced.
You have direct access to the user's Google Calendar.""",

    "writing": """You are a professional writer and editor with expertise across all formats:
emails, reports, presentations, speeches, social media, and creative writing.
You match the user's voice, improve clarity, and tailor content to the audience.
Review email history to match the user's communication style.""",

    "technical": """You are a senior software engineer and technical architect.
You help with code review, debugging, system design, technology selection,
and explaining complex technical concepts to both technical and non-technical audiences.
You have access to the user's email and calendar for technical project context.""",
}

_DEFAULT_SYSTEM = """You are a highly capable specialist assistant.
You have deep expertise in the topic at hand. Be thorough, accurate, and actionable.
You have access to the user's email, calendar, and SMS to provide full context."""

# ── Tool registry ─────────────────────────────────────────────────────────────

def _build_tools() -> list[dict]:
    tools = []
    if config.SMS_ENABLED:
        tools.extend(sms_tool.SMS_TOOLS)
    if config.EMAIL_ENABLED:
        tools.extend(email_tool.EMAIL_TOOLS)
    if config.CALENDAR_ENABLED:
        tools.extend(calendar_tool.CALENDAR_TOOLS)
    return tools


# ── Specialist agent ──────────────────────────────────────────────────────────

class SpecialistAgent(BaseAgent):
    """
    A dynamically created specialist agent.
    Initialized with a type (e.g. 'finance'), a task description, and optional context.
    """

    def __init__(
        self,
        specialist_type: str,
        task: str,
        context: str,
        memory: MemoryStore,
    ):
        super().__init__(memory)
        self.specialist_type = specialist_type
        self.task = task
        self.context = context
        self.name = f"specialist:{specialist_type}"
        self.tools = _build_tools()

    @property
    def system_prompt(self) -> str:
        base = _SYSTEM_PROMPTS.get(self.specialist_type, _DEFAULT_SYSTEM)
        return (
            f"{base}\n\n"
            f"## Your Current Task\n{self.task}\n\n"
            f"## Additional Context\n{self.context or 'None provided.'}"
        )

    def _execute_tool(self, tool_name: str, tool_input: dict[str, Any]) -> Any:
        if tool_name in ("send_sms", "get_recent_sms"):
            return sms_tool.execute(tool_name, tool_input)
        if tool_name in ("read_emails", "send_email", "search_emails"):
            return email_tool.execute(tool_name, tool_input)
        if tool_name in ("get_events", "create_event", "delete_event"):
            return calendar_tool.execute(tool_name, tool_input)
        raise ValueError(f"Unknown tool: {tool_name}")

    def run_and_save(self) -> str:
        """Run the specialist and save the result as a handoff note in shared memory."""
        initial_messages = [{"role": "user", "content": self.task}]
        result = self.run(initial_messages)
        self.memory.add_handoff(
            specialist_type=self.specialist_type,
            original_query=self.task,
            summary=result[:1000],  # Store first 1000 chars as summary
        )
        return result
