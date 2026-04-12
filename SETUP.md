# Setup Instructions

## Quick Start

### 1. Create Discord Bot & Get Token

1. Go to [Discord Developer Portal](https://discord.com/developers/applications)
2. Click "New Application"
3. Go to "Bot" section → "Add Bot"
4. Copy the bot token (keep it secret!)
5. Go to "OAuth2" → "URL Generator"
6. Select scopes: `bot`
7. Select permissions: `Send Messages`, `Embed Links`, `Read Message History`
8. Copy the generated URL and open it to invite bot to your server
9. Add bot to your `#cw-ticketing` channel

### 2. Get ConnectWise Credentials

Contact your ConnectWise administrator for:
- **Company ID** (e.g., "superiornet")
- **Public Key**
- **Private Key**
- **Client ID** (UUID format)
- **Member ID** (numeric, for time entries)

Add these to your config file.

### 3. Setup Python Environment

```bash
# Clone repo
git clone https://github.com/your-org/discord-cw-ticket-bot.git
cd discord-cw-ticket-bot

# Create venv
python3 -m venv venv
source venv/bin/activate  # or: venv\Scripts\activate (Windows)

# Install dependencies
pip install discord.py requests anthropic
```

### 4. Configure

```bash
# Copy template
cp config/discord_cw_ticket_config.json.template config/discord_cw_ticket_config.json

# Edit with your credentials
nano config/discord_cw_ticket_config.json
```

Fill in:
- `discord_channel_id`: Right-click channel in Discord → "Copy Channel ID"
- `discord_guild_id`: Right-click server → "Copy Guild ID"
- `cw_company`: Your ConnectWise company ID
- `cw_public_key`: Your public key
- `cw_private_key`: Your private key
- `cw_client_id`: Your UUID client ID
- `cw_member_id`: Your numeric member ID (for time entries)
- `company_mapping`: Map of client names to company IDs

### 5. Get Discord Channel & Guild IDs

In Discord:
1. Enable Developer Mode (Settings → Advanced → Developer Mode)
2. Right-click channel → "Copy Channel ID"
3. Right-click server → "Copy Guild ID"

### 6. Set Discord Bot Token

The bot loads its token from the `DISCORD_BOT_TOKEN` environment variable:

```bash
export DISCORD_BOT_TOKEN="your_discord_token_here"
```

**Never commit the token to git.** Store it in a `.env` file (listed in `.gitignore`) or use a secrets manager.

### 7. Run

**Direct:**
```bash
export DISCORD_BOT_TOKEN="your_token"
python3 discord_ticket_bot.py
```

**As systemd service (Linux):**

1. Create a `.env` file in the bot directory:
```bash
echo "DISCORD_BOT_TOKEN=your_token_here" > .env
chmod 600 .env
```

2. Update the service file to load the env file:
```bash
sudo cp discord-ticket-bot.service /etc/systemd/system/
# Edit the service file and add:
# EnvironmentFile=/path/to/.env
```

3. Enable and start:
```bash
sudo systemctl daemon-reload
sudo systemctl enable discord-ticket-bot
sudo systemctl start discord-ticket-bot
sudo systemctl status discord-ticket-bot
```

## Configuration Deep Dive

### discord_cw_ticket_config.json

```json
{
  "discord_channel_id": "1491487503339884825",
  "discord_guild_id": "445019596139921408",
  "discord_channel_name": "cw-ticketing",
  "cw_base_url": "https://na.myconnectwise.net/v4_6_release/apis/3.0",
  "cw_company": "your_cw_company_id",
  "cw_public_key": "your_public_key",
  "cw_private_key": "your_private_key",
  "cw_client_id": "your_client_id",
  "cw_member_id": 147,
  "anthropic_api_key": "sk-ant-...",
  "default_priority_id": 8,
  "default_priority_name": "Medium",
  "company_mapping": {
    "Client A": 12345,
    "Client B": 12346,
    "Client C": 12347,
    "Client D": 12348
  },
  "priority_ids": {
    "critical": 6,
    "high": 15,
    "medium": 8,
    "low": 7
  }
}
```

### Getting Company IDs from ConnectWise

```python
import requests
import base64

company = "superiornet"
public_key = "YOUR_KEY"
private_key = "YOUR_KEY"
client_id = "YOUR_UUID"

auth = base64.b64encode(f"{company}+{public_key}:{private_key}".encode()).decode()

headers = {
    "Authorization": f"Basic {auth}",
    "clientId": client_id,
    "Accept": "application/json"
}

# Get all companies
resp = requests.get(
    "https://na.myconnectwise.net/v4_6_release/apis/3.0/company/companies",
    headers=headers
)

for company in resp.json():
    print(f"{company['name']}: {company['id']}")
```

### Getting Member ID

```python
# From same API call above, list members:
resp = requests.get(
    "https://na.myconnectwise.net/v4_6_release/apis/3.0/system/members",
    headers=headers
)

for member in resp.json():
    print(f"{member['firstName']} {member['lastName']}: {member['id']}")
```

## Testing

### Test Bot Connection

```bash
python3
>>> import discord
>>> bot = discord.Bot()
>>> bot.run("YOUR_TOKEN_HERE")
```

### Test ConnectWise API

```bash
python3
>>> from discord_cw_module import DiscordTicketBotV2
>>> import json
>>> config = json.load(open('config/discord_cw_ticket_config.json'))
>>> bot_cog = DiscordTicketBotV2(None, config)
>>> bot_cog.create_ticket(12345, "Test Client", "Test Subject", "Test Description", 8, "Medium")
```

### Manual Test Message in Discord

Just type in the channel:
```
Client A
```

Bot should respond:
```
📋 Subject for Client A?
```

## Troubleshooting

### Bot doesn't respond to messages

1. Check bot is in channel: Settings → Integrations → Bots
2. Check bot has "Send Messages" permission
3. Check channel ID is correct in config
4. Run `systemctl status discord-ticket-bot` to see logs

### ConnectWise API errors (400, 401)

1. Verify credentials are correct
2. Check company ID format (usually numeric)
3. Ensure Base64 encoding matches ConnectWise format
4. Check if account has API access enabled

### Time entry creation fails

1. Verify `cw_member_id` exists and has time tracking permissions
2. Check if member is active (not archived/deactivated)
3. Ensure ticket exists before creating entry

### Logs

**Systemd:**
```bash
sudo journalctl -u discord-ticket-bot -f  # Follow live
sudo journalctl -u discord-ticket-bot -n 50  # Last 50 lines
```

**Direct run:**
Check console output for `[timestamp] message` format

## Security

⚠️ **Never commit your config file with secrets!**

```bash
# Add to .gitignore
echo "config/discord_cw_ticket_config.json" >> .gitignore
```

**Alternative: Use environment variables**

```python
import os

config = {
    "cw_public_key": os.getenv("CW_PUBLIC_KEY"),
    "cw_private_key": os.getenv("CW_PRIVATE_KEY"),
    # ...
}
```

Then set env vars before running:
```bash
export CW_PUBLIC_KEY="..."
export CW_PRIVATE_KEY="..."
python3 discord_ticket_bot.py
```

## Support

For issues, feature requests, or questions:
- Open a GitHub issue
- Contact your MSP administrator

