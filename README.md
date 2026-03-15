# Personal Assistant / Chief of Staff Agent

A CLI-based personal assistant powered by Claude. Acts as your Chief of Staff — it reads your SMS, email, and calendar, and can spin up specialist sub-agents (finance, travel, health, scheduling, and more) on demand. All agents share a persistent SQLite memory.

## Architecture

```
User (CLI)
    │
    ▼
Chief of Staff Agent  (claude-sonnet-4-6)
    ├── Tools: SMS (Twilio) · Email (Outlook) · Calendar (Google)
    ├── Tool: save_fact          → writes to shared SQLite memory
    └── Tool: delegate_to_specialist
                │
                ▼
        Specialist Agent  (same model, focused system prompt)
            ├── Types: finance · travel · health · legal · research
            │          scheduling · writing · technical
            ├── Same tool access (SMS, email, calendar)
            └── Writes handoff summary → shared SQLite memory
```

All agents read from and write to the same `data/memory.db` SQLite database, so context is preserved across the entire session and between runs.

## Integrations

| Integration | Provider | Setup |
|---|---|---|
| SMS | Twilio | Account SID + Auth Token + phone number |
| Email | Microsoft Outlook (Graph API) | Azure app registration (device flow) |
| Calendar | Google Calendar | OAuth2 credentials JSON (Desktop app) |

All integrations are optional — the agent gracefully degrades if credentials are missing.

## Setup

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure credentials

```bash
cp .env.example .env
# Edit .env with your API keys
```

**Anthropic** (required):
- Get your API key at https://console.anthropic.com

**Twilio SMS** (optional):
- Sign up at https://www.twilio.com
- Buy a phone number
- Copy Account SID, Auth Token, and your Twilio number

**Microsoft Outlook** (optional):
1. Go to https://portal.azure.com → Azure Active Directory → App registrations
2. Register a new app, select "Accounts in any organizational directory and personal Microsoft accounts"
3. Under Authentication, add a Mobile and Desktop platform with redirect URI: `https://login.microsoftonline.com/common/oauth2/nativeclient`
4. Under API permissions, add: `Mail.Read`, `Mail.Send`, `User.Read` (all delegated)
5. Copy the Application (client) ID → `AZURE_CLIENT_ID` in `.env`

**Google Calendar** (optional):
1. Go to https://console.cloud.google.com
2. Create a project and enable the Google Calendar API
3. Go to Credentials → Create Credentials → OAuth 2.0 Client IDs → Desktop app
4. Download the JSON file and save it as `google_credentials.json`

### 3. Run

```bash
# Standard chat mode
python main.py

# With SMS polling (checks for new inbound texts every 30s)
python main.py --sms-mode

# Minimal output (no rich formatting)
python main.py --brief
```

On first run with Microsoft or Google credentials, you'll be prompted to authenticate via browser/device code. Tokens are cached locally for subsequent runs.

## Example Interactions

```
You: What's on my calendar this week?
You: Read my last 5 unread emails
You: Send a text to +14155552671: "Running 10 minutes late"
You: Help me plan a trip to Tokyo in April        → travel specialist
You: Analyze my Q1 expenses from my inbox         → finance specialist
You: Draft a reply to Sarah's email about the proposal  → writing specialist
You: Remember that I prefer window seats on flights     → saved to memory
```

## Memory

The agent persists context in `data/memory.db` (SQLite):

- **messages** — full conversation history with timestamps
- **facts** — key facts about you (preferences, contacts, routines)
- **handoffs** — summaries of what each specialist agent produced

## File Structure

```
├── main.py                   # CLI entry point
├── config.py                 # Environment variable loading
├── requirements.txt
├── .env.example
├── agents/
│   ├── base_agent.py         # Tool-use loop + memory injection
│   ├── chief_of_staff.py     # Main orchestrator
│   └── specialist.py         # Domain specialist factory
├── tools/
│   ├── sms_tool.py           # Twilio integration
│   ├── email_tool.py         # Microsoft Graph (Outlook)
│   └── calendar_tool.py      # Google Calendar
├── memory/
│   └── store.py              # SQLite shared memory
└── data/
    └── memory.db             # Auto-created on first run
```
