"""
Personal Assistant / Chief of Staff — CLI entry point.

Usage:
    python main.py               # Standard chat mode
    python main.py --sms-mode    # Poll for incoming SMS every 30s in background
    python main.py --brief       # Minimal output (no panels)
"""
from __future__ import annotations

import argparse
import sys
import threading
import time

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.markdown import Markdown
    from rich.prompt import Prompt
    from rich.rule import Rule
    from rich.text import Text
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False

from memory.store import MemoryStore
from agents.chief_of_staff import ChiefOfStaffAgent
import config

console = Console() if RICH_AVAILABLE else None


# ── Display helpers ────────────────────────────────────────────────────────────

def print_welcome():
    if not RICH_AVAILABLE or args.brief:
        print("\n=== Personal Assistant / Chief of Staff ===")
        print("Type 'exit' or 'quit' to stop.\n")
        return

    console.print(Panel.fit(
        "[bold cyan]Personal Assistant[/bold cyan] · [dim]Chief of Staff[/dim]\n"
        "[dim]SMS · Email · Calendar · Specialist Agents[/dim]",
        border_style="cyan",
        padding=(1, 4),
    ))

    enabled = []
    if config.SMS_ENABLED:
        enabled.append("[green]SMS[/green]")
    else:
        enabled.append("[dim]SMS (not configured)[/dim]")
    if config.EMAIL_ENABLED:
        enabled.append("[green]Email[/green]")
    else:
        enabled.append("[dim]Email (not configured)[/dim]")
    if config.CALENDAR_ENABLED:
        enabled.append("[green]Calendar[/green]")
    else:
        enabled.append("[dim]Calendar (not configured)[/dim]")

    console.print("  Integrations: " + " · ".join(enabled))
    console.print("  Type [bold]'exit'[/bold] or [bold]'quit'[/bold] to stop.\n")


def print_user_line(text: str):
    if RICH_AVAILABLE and not args.brief:
        console.print(f"\n[bold blue]You[/bold blue]  {text}")
    else:
        print(f"\nYou: {text}")


def print_assistant(text: str):
    if RICH_AVAILABLE and not args.brief:
        console.print(Rule("[dim]Assistant[/dim]", style="dim"))
        console.print(Markdown(text))
        console.print()
    else:
        print(f"\nAssistant: {text}\n")


def print_error(text: str):
    if RICH_AVAILABLE:
        console.print(f"[bold red]Error:[/bold red] {text}")
    else:
        print(f"Error: {text}", file=sys.stderr)


def get_input(prompt: str = "You") -> str:
    if RICH_AVAILABLE and not args.brief:
        return Prompt.ask(f"\n[bold blue]{prompt}[/bold blue]")
    return input(f"\n{prompt}: ").strip()


# ── SMS polling (background thread) ───────────────────────────────────────────

_last_sms_sid: str | None = None


def _sms_poller(agent: ChiefOfStaffAgent, interval: int = 30):
    """Background thread: polls Twilio every `interval` seconds for new inbound SMS."""
    global _last_sms_sid
    if RICH_AVAILABLE:
        console.print("[dim]SMS polling active (every 30s)[/dim]")
    while True:
        time.sleep(interval)
        try:
            from tools.sms_tool import get_recent_sms
            messages = get_recent_sms(limit=5, direction="inbound")
            if messages and messages[0]["sid"] != _last_sms_sid:
                new_msgs = []
                for m in messages:
                    if m["sid"] == _last_sms_sid:
                        break
                    new_msgs.append(m)

                if new_msgs:
                    _last_sms_sid = messages[0]["sid"]
                    for m in reversed(new_msgs):
                        notification = (
                            f"[INCOMING SMS from {m['from']}]: {m['body']}"
                        )
                        if RICH_AVAILABLE:
                            console.print(f"\n[bold yellow]New SMS[/bold yellow] from {m['from']}: {m['body']}")
                        agent.memory.add_message("user", "sms_inbound", notification)
        except Exception as exc:
            if RICH_AVAILABLE:
                console.print(f"[dim red]SMS poll error: {exc}[/dim red]")


# ── Main chat loop ─────────────────────────────────────────────────────────────

def build_messages(memory: MemoryStore, new_user_input: str) -> list[dict]:
    """
    Build the messages array for the current turn.
    We pass the last N message pairs from memory plus the new user input.
    """
    history = memory.get_recent_messages(n=20)

    messages: list[dict] = []
    for m in history:
        if m["role"] == "user":
            messages.append({"role": "user", "content": m["content"]})
        elif m["role"] == "assistant":
            messages.append({"role": "assistant", "content": m["content"]})

    # Ensure conversation starts with a user message (API requirement)
    if not messages or messages[-1]["role"] == "assistant":
        messages.append({"role": "user", "content": new_user_input})
    elif messages[-1]["role"] == "user":
        # Merge with previous if back-to-back user messages
        messages.append({"role": "user", "content": new_user_input})

    return messages


def main():
    memory = MemoryStore()
    agent = ChiefOfStaffAgent(memory=memory)

    print_welcome()

    # Optional: start SMS polling thread
    if args.sms_mode and config.SMS_ENABLED:
        t = threading.Thread(target=_sms_poller, args=(agent,), daemon=True)
        t.start()
    elif args.sms_mode and not config.SMS_ENABLED:
        print_error("--sms-mode requires TWILIO_* credentials in .env")

    while True:
        try:
            user_input = get_input()
        except (EOFError, KeyboardInterrupt):
            if RICH_AVAILABLE:
                console.print("\n[dim]Goodbye.[/dim]")
            else:
                print("\nGoodbye.")
            break

        if not user_input:
            continue

        if user_input.lower() in ("exit", "quit", "bye"):
            if RICH_AVAILABLE:
                console.print("[dim]Goodbye.[/dim]")
            else:
                print("Goodbye.")
            break

        # Save user message to memory
        memory.add_message("user", "user", user_input)

        # Build messages and run the agent
        messages = build_messages(memory, user_input)
        try:
            response = agent.run(messages)
            print_assistant(response)
        except Exception as exc:
            print_error(str(exc))


# ── Entry point ────────────────────────────────────────────────────────────────

parser = argparse.ArgumentParser(description="Personal Assistant / Chief of Staff")
parser.add_argument(
    "--sms-mode",
    action="store_true",
    help="Poll Twilio for incoming SMS messages every 30 seconds in the background.",
)
parser.add_argument(
    "--brief",
    action="store_true",
    help="Minimal output without rich formatting.",
)
args = parser.parse_args()

if __name__ == "__main__":
    main()
