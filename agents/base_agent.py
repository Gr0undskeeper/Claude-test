"""
Base agent class.
Implements the Anthropic SDK tool-use loop and shared memory injection.
All agents (Chief of Staff and specialists) extend this class.
"""
from __future__ import annotations

import json
from typing import Any

import anthropic

import config
from memory.store import MemoryStore

_client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)


class BaseAgent:
    """
    Abstract base for all agents.

    Subclasses must implement:
        name        : str  — agent identifier written to memory
        system_prompt : str  — base system prompt (memory context is appended automatically)
        tools       : list  — Anthropic tool-schema dicts
        _execute_tool(name, input) -> Any   — dispatch tool calls
    """

    name: str = "base"
    tools: list[dict] = []

    def __init__(self, memory: MemoryStore):
        self.memory = memory

    # ── Override in subclasses ─────────────────────────────────────────────────

    @property
    def system_prompt(self) -> str:
        raise NotImplementedError

    def _execute_tool(self, tool_name: str, tool_input: dict[str, Any]) -> Any:
        raise NotImplementedError

    # ── Core loop ──────────────────────────────────────────────────────────────

    def run(self, messages: list[dict]) -> str:
        """
        Run the agent with the provided message history.
        Loops until the model produces a final text response (stop_reason == 'end_turn').
        Returns the final text.
        """
        system = self._build_system()
        working_messages = list(messages)

        while True:
            response = _client.messages.create(
                model=config.CLAUDE_MODEL,
                max_tokens=4096,
                system=system,
                tools=self.tools,
                messages=working_messages,
            )

            # Collect all text blocks for final response
            text_blocks = [
                block.text
                for block in response.content
                if block.type == "text"
            ]

            if response.stop_reason == "end_turn":
                final_text = "\n".join(text_blocks).strip()
                self.memory.add_message("assistant", self.name, final_text)
                return final_text

            if response.stop_reason == "tool_use":
                # Append assistant message with all content blocks
                working_messages.append(
                    {"role": "assistant", "content": response.content}
                )

                # Execute each tool call and collect results
                tool_results = []
                for block in response.content:
                    if block.type == "tool_use":
                        result = self._safe_execute_tool(block.name, block.input)
                        tool_results.append(
                            {
                                "type": "tool_result",
                                "tool_use_id": block.id,
                                "content": json.dumps(result, default=str),
                            }
                        )

                working_messages.append({"role": "user", "content": tool_results})
                continue

            # Unexpected stop reason — return whatever text we have
            return "\n".join(text_blocks).strip() or "(No response)"

    def _safe_execute_tool(self, tool_name: str, tool_input: dict) -> Any:
        try:
            return self._execute_tool(tool_name, tool_input)
        except Exception as exc:
            return {"error": str(exc)}

    def _build_system(self) -> str:
        context = self.memory.build_context_block()
        return f"{self.system_prompt}\n\n---\n## Shared Memory Context\n{context}"
