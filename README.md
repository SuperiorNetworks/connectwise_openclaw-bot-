# ConnectWise Discord Ticket Bot (Miles)

A conversational Discord bot that acts as an intelligent bridge between Discord and ConnectWise Manage. It uses natural language processing (and Claude AI) to parse free-form messages into structured ConnectWise tickets, schedule entries, and ticket notes.

**Vision:** This project is evolving into a specialized ConnectWise sub-agent. The goal is to build an agent that masters natural language intent matching, provides constructive feedback to users on how to improve their prompts, and can eventually be tasked by a "Master Agent" virtual assistant to handle all ConnectWise-specific operations throughout the day. See the [Roadmap](ROADMAP.md) for details.

**Current Version:** v2.6.0

---

## Key Features

### Dual-Mode Behavior

| Where you message Miles | What it does |
|---|---|
| **`#cw-ticketing` channel** | ConnectWise only — creates tickets, logs time, updates tickets |
| **Direct Message to Miles** | Full conversational assistant with persistent memory |
| **`@Miles` in any other channel** | Full conversational assistant with persistent memory |
| **Dedicated assistant channels** (e.g. `#nyc-2026`) | Full conversational assistant — responds to **every** message, no `@mention` needed |

### ConnectWise Features (`#cw-ticketing`)

- **Live ConnectWise Client Sync:** The bot pulls your full active company list directly from ConnectWise on startup and auto-refreshes it every 24 hours in the background. No more hardcoding client names in a config file!
- **One-Shot Ticket Creation:** Type a single message like `"Create a ticket for Positive Electric with subject Server Down, description Main file server offline, schedule for tomorrow at 2pm, 5 hours, high priority"` and the bot extracts all fields and creates the ticket instantly.
- **Conversational Fallback:** If you just type `"Positive Electric"`, the bot will ask you step-by-step for the subject, description, and time to log.
- **Smart Ticket Updates:** Type `add to ticket 31666 - Rebooted the server`, `#31666`, or just `31666` to append notes directly to the ConnectWise ticket's Discussion tab.
- **File & Image Uploads:** Paste images, PDFs, Word documents, or any other file directly into Discord while creating or updating a ticket, and the bot automatically uploads them to the ConnectWise ticket's Documents tab.
- **Miles / AI Command System:** Prefix any message with `Miles:` or `AI:` to trigger Claude AI for tasks like summarizing tickets, translating text, or formatting notes.
- **Natural Language Dates:** Understands "tomorrow at 2pm", "next Friday", "in 3 hours", etc.
- **Deep Linking:** Generates direct `v2025_1` ConnectWise deep links for every created or updated ticket.

---

## Usage Guide

### 1. Create a New Ticket

You can provide all information at once, or let the bot guide you.

*(Note: You can type `cancel`, `stop`, or `abort` at any point during a conversational flow to cleanly exit without creating a ticket.)*

**Conversational Flow:**
```text
You: Positive Electric
Bot: 📋 Subject for Positive Electric?
You: Server down
Bot: 📝 Description/Details?
You: Main file server offline, preventing access to shared drives
Bot: ⏱️ Time to log? (or 'skip')
You: 5 hours
Bot: ✅ Ticket #31642 Created
```

**One-Shot Flow:**
```text
You: Create a ticket for Positive Electric. Subject: Server down. Description: Main file server offline. Log 5 hours.
Bot: ✅ Ticket #31642 Created
```

### 2. Add a Note to an Existing Ticket

You can reference a ticket using `#12345`, `ticket 12345`, `add to ticket 12345`, or just a bare 5-digit number like `12345`.

**Direct Note:**
```text
You: add to ticket 31666 - I rebooted the server and ran diagnostics
Bot: ⏱️ Time to log? (or 'skip')
You: 2.5 hours
Bot: ✅ Note Added to Ticket #31666
```

**Conversational Note:**
```text
You: #31666
Bot: 📝 What update should I add to ticket #31666?
You: Server is back online
Bot: ⏱️ Time to log? (or 'skip')
You: skip
Bot: ✅ Note Added to Ticket #31666
```

**Bare Number Note:**
```text
You: add these ups labels 31671
Bot: 📝 What update should I add to ticket #31671?
```

### 3. Miles / AI Commands

Prefix any message with `Miles:` or `AI:` to trigger the AI command system.

| Command | Description |
|---|---|
| `Miles: help` | Posts the command reference list |
| `Miles: refresh clients` | Forces an immediate live sync of the company list from ConnectWise |
| `Miles: client count` | Shows how many active clients are loaded and when the last sync occurred |
| `Miles: summarize ticket 31666` | Fetches the ticket and posts a Claude-written 2-3 sentence summary |
| `Miles: translate to Spanish` | Translates the text above the command to Spanish |
| `Miles: add a priority note at the top` | Prepends a `⚠️ PRIORITY` header to the text above |
| `Miles: list in bullet style` | Formats the text above as a bullet list before posting |
| `Miles: numbered list` | Formats the text above as a numbered list before posting |
| `Miles: send to AI <question>` | Free-form question — Claude responds directly in Discord |

**Combining AI commands with ticket notes:**
You can put an instruction on the last line of a ticket update. The bot will strip the instruction, format the note, and post it to ConnectWise.
```text
You: add to ticket 31666 - Rebooted router
Cleared DNS cache
All systems nominal
Miles: list in bullet style

Bot: ✅ Note Added to Ticket #31666 (Formatted as a bulleted list)
```

---

## Setup & Installation

### 1. Prerequisites
- Python 3.10+
- A Discord Bot Token (with Message Content Intent enabled)
- ConnectWise Manage API Credentials (Public/Private Key, Client ID)
- Anthropic API Key (for Claude AI features)

### 2. Installation
```bash
git clone https://github.com/SuperiorNetworks/connectwise_openclaw-bot-.git
cd connectwise_openclaw-bot-
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install anthropic  # Required for AI features
```

### 3. Configuration
Copy the template config file and add your credentials:
```bash
cp config/discord_cw_ticket_config.json.template config/discord_cw_ticket_config.json
```

Edit `config/discord_cw_ticket_config.json`:
```json
{
  "discord_token": "YOUR_DISCORD_BOT_TOKEN",
  "discord_channel_id": "123456789012345678",
  "cw_base_url": "https://na.myconnectwise.net/v4_6_release/apis/3.0",
  "cw_company": "your_cw_company_id",
  "cw_public_key": "your_public_key",
  "cw_private_key": "your_private_key",
  "cw_client_id": "your_client_id",
  "anthropic_api_key": "sk-ant-...",
  "company_mapping": {
    "Client A": 12345,
    "Client B": 12346
  }
}
```
*(Note: Do not commit your actual config file to version control. It is ignored by `.gitignore`.)*

### 4. Running the Bot
```bash
python3 discord_ticket_bot.py
```

---

## Systemd Service Deployment (Linux)

To run the bot continuously in the background on a Linux server:

1. Edit `discord-ticket-bot.service` to match your installation paths.
2. Copy it to systemd:
   ```bash
   sudo cp discord-ticket-bot.service /etc/systemd/system/
   ```
3. Enable and start the service:
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable discord-ticket-bot
   sudo systemctl start discord-ticket-bot
   ```

---

## License & Support

© 2026 Superior Networks LLC
Contact: Your MSP Administrator
