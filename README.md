# Discord Conversational Ticket Bot for ConnectWise

A flexible, conversational Discord bot that creates and updates ConnectWise service tickets with natural language input—no rigid format required.

## Features

- **Conversational Flow**: Ask clarifying questions instead of rigid formats
- **Flexible Input**: Start with a client name or ticket number—bot guides the rest
- **Time Tracking**: Automatically creates billable time entries when hours are specified
- **Context Aware**: Maintains per-user conversation state; switch between create/update mid-conversation
- **Deep Links**: Generates proper ConnectWise v2025_1 deep links with LZMA compression
- **Smart Parsing**: Auto-detects priorities, extracts time notation (hours/minutes), finds client names
- **Error Handling**: Graceful error responses with actionable feedback

## Installation

### Prerequisites

- Python 3.9+
- discord.py
- requests

### Setup

1. **Clone or copy the module:**
   ```bash
   git clone https://github.com/your-org/discord-cw-ticket-bot.git
   cd discord-cw-ticket-bot
   ```

2. **Create virtual environment:**
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies:**
   ```bash
   pip install discord.py requests
   ```

4. **Configure:**
   - Copy `config/discord_cw_ticket_config.json.template` → `config/discord_cw_ticket_config.json`
   - Edit with your ConnectWise credentials and Discord settings:
     ```json
     {
       "discord_channel_id": "YOUR_CHANNEL_ID",
       "discord_guild_id": "YOUR_GUILD_ID",
       "cw_base_url": "https://na.myconnectwise.net/v4_6_release/apis/3.0",
       "company_mapping": {
         "Client A": 12345,
         "Client B": 12346
       },
       "priority_ids": {
         "critical": 6,
         "high": 15,
         "medium": 8,
         "low": 7
       }
     }
     ```

5. **Run:**
   ```bash
   python3 discord_ticket_listener_v2.py
   ```

## Usage

### Create a New Ticket

```
You: Client A
Bot: 📋 Subject for Client A?

You: Server down
Bot: 📝 Description/Details?

You: Main file server offline, preventing access to shared drives
Bot: ⏱️ Time to log? (or 'skip')

You: 5 hours
Bot: ✅ Ticket #31642 Created
     Client: Client A
     Priority: Medium
     Time: 5.0 hours
```

### Add Note to Existing Ticket

```
You: #31641
Bot: 📝 Note to add?

You: I rebooted the server and ran diagnostics
Bot: ⏱️ Time to log? (or 'skip')

You: 2.5 hours
Bot: ✅ Note Added to Ticket #31641
     Time Entry: ✅ 2.5 hours
```

### Switch Conversations Mid-Flow

```
You: [In middle of creating ticket for Company A]
You: New ticket for Client B
Bot: [Abandons Company A flow, starts new for Adaptive Development]

OR

You: #31641
Bot: [Switches to update mode for ticket #31641]
```

## Configuration

### discord_cw_ticket_config.json

```json
{
  "discord_channel_id": "1491487503339884825",
  "discord_guild_id": "445019596139921408",
  "discord_channel_name": "cw-ticketing",
  "cw_base_url": "https://na.myconnectwise.net/v4_6_release/apis/3.0",
  "default_priority_id": 8,
  "default_priority_name": "Medium",
  "company_mapping": {
    "Client A": 12345,
    "Client B": 12346,
    "Client C": 12347
  },
  "priority_ids": {
    "critical": 6,
    "high": 15,
    "medium": 8,
    "low": 7
  }
}
```

## Conversation Flow States

### Create Ticket Flow
```
company → subject → description → time → [TICKET CREATED]
```

### Update Ticket Flow
```
ticket_id → note → time → [NOTE + TIME ENTRY CREATED]
```

### Mid-Conversation Switches
- Saying "New ticket for [Client]" switches to create flow
- Saying "#[number]" switches to update flow
- Previous conversation state is discarded

## API Integration

### ConnectWise Endpoints Used

| Operation | Endpoint | Method |
|-----------|----------|--------|
| Create Ticket | `/service/tickets` | POST |
| Add Note | `/service/tickets/{id}/notes` | POST |
| Create Time Entry | `/schedule/entries` | POST |

### Authentication

Uses Basic Auth with ConnectWise credentials:
```
Authorization: Basic base64(company+public_key:private_key)
clientId: [uuid]
```

## Features Detail

### Smart Priority Detection
Automatically detects priority from description:
- `critical` / `p1` → Critical
- `high` / `p2` → High
- `medium` / `p3` → Medium (default)
- `low` / `p4` → Low

### Time Notation Parsing
Supports flexible time input:
- `5 hours` → 5.0
- `2.5 hrs` → 2.5
- `30 minutes` → 0.5
- `90 mins` → 1.5

### Deep Link Generation
Generates v2025_1 format deep links:
- JSON state object with ticket ID, member, timestamp
- LZMA compression (512KB dictionary)
- Custom Base64 encoding (ConnectWise alphabet)
- Direct browser access via `https://na.myconnectwise.net/v2025_1/...`

## Error Handling

- **Client not found**: Asks user to clarify which client
- **Invalid time format**: Suggests correct format
- **API errors**: Graceful fallback with error details
- **Schedule entry failures**: Ticket created successfully, warns about time entry

## Systemd Service (Optional)

Deploy as background service on Linux:

```ini
[Unit]
Description=Discord CW Ticket Bot
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/path/to/bot
ExecStart=/path/to/venv/bin/python3 discord_ticket_listener_v2.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable:
```bash
sudo systemctl enable discord-ticket-bot
sudo systemctl start discord-ticket-bot
```

## Logging

Bot logs to stdout/journal with timestamps:
```
[2026-04-08T22:45:31.123456] User.name: Positive Electric
✅ Created ticket #31642 for Positive Electric + 5.0h time entry
```

## Token Cost

- **Per-action estimate**: ~450 tokens (5 conversation exchanges)
- **Compare to rigid format**: ~230 tokens (single message parse)
- **Trade-off**: More tokens for zero format restrictions

## License

© 2026 Superior Networks LLC

## Support

Contact: Your MSP Administrator
