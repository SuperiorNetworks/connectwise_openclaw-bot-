# Quick Start: Discord Ticket Bot for Your MSP

This bot makes it easy to create and update service tickets in ConnectWise right from Discord—no forms, no portals, just chat.

## Getting Started (5 minutes)

### Step 1: Join the Ticket Channel
Your MSP will add your team to the `#cw-ticketing` Discord channel. That's where the bot lives.

### Step 2: Create Your First Ticket
Just type a client name:
```text
Your Client Name
```

The bot will walk you through the rest:
```text
Bot: 📋 Subject for Your Client Name?
You: Server down
Bot: 📝 Description/Details?
You: Main server offline, users can't access files
Bot: ⏱️ Time to log? (or 'skip')
You: 2 hours
Bot: ✅ Ticket #31642 Created
```

That's it. Your ticket is in ConnectWise.

---

## Common Tasks

### Create a Ticket (One-Shot)
You don't have to wait for the bot to ask questions. You can provide everything at once:
```text
Create a ticket for Your Client Name. Subject: Server down. Description: Main server offline. Log 2 hours.
```

### Add Notes to an Existing Ticket
You can add notes to a ticket using the ticket number.

**Direct Note:**
```text
add to ticket 31641 - Followed up with client; all systems stable
```

**Conversational Note:**
```text
You: #31641
Bot: 📝 What update should I add to ticket #31641?
You: Followed up with client; all systems stable
Bot: ⏱️ Time to log? (or 'skip')
You: 30 minutes
```

**Bare Number Note:**
```text
You: add these ups labels 31671
Bot: 📝 What update should I add to ticket #31671?
```

### Upload Files & Images

If you need to share a screenshot, photo, PDF, Word document, or any other file, just paste it into Discord while creating or updating a ticket. The bot will automatically upload it to the ConnectWise ticket's Documents tab.
### Cancel a Ticket
If you start creating a ticket but change your mind, just type `cancel`, `stop`, or `abort` at any point.

---

## Writing Your Notes

Keep it clear and direct:

✅ **Good:**
```text
• Server was offline
• I rebooted it and checked diagnostics
• Everything's working now
```

❌ **Bad:**
```text
Did some stuff and fixed it
```

### Include Hardware/Software Names
✅ Better: "Replaced SSD with Samsung 870 EVO"  
❌ Vague: "Replaced hard drive"

### Include Time If You Worked On It
The bot accepts:
- `2 hours`
- `1.5 hrs`
- `30 minutes`
- `45 mins`

---

## Miles / AI Commands

You can ask the bot (Miles) to help you format notes or summarize tickets by starting your message with `Miles:` or `AI:`.

| Command | What it does |
|---|---|
| `Miles: summarize ticket 31641` | Posts a quick summary of the ticket |
| `Miles: list in bullet style` | Formats your note as a bulleted list before posting |
| `Miles: translate to Spanish` | Translates your text to Spanish |

**Example:**
```text
add to ticket 31641 - Rebooted server
Checked logs
Everything is fine
Miles: list in bullet style
```
*(The bot will format your note as a bulleted list and add it to the ticket.)*

---

## What Happens After You Submit?
1. **Ticket is created** in ConnectWise automatically
2. **Time is logged** (if you included hours)
3. **Bot sends you a link** to view the ticket
4. **Your MSP can see it immediately** and assign it if needed

## Troubleshooting

### Bot doesn't respond
1. Make sure you're in the `#cw-ticketing` channel
2. Make sure the bot is in the channel (ask your MSP)
3. Check your typing—start with a client name or ticket number

### Bot says "Client not recognized"
Make sure you use the exact client name your MSP set up. Ask if unsure.

### Can't find a ticket number?
- Check ConnectWise directly
- Ask your MSP for the ticket ID
- Or just start a new ticket

## Questions?
Contact your MSP support team. They control the bot and can help troubleshoot.

---
**Created by Superior Networks LLC**  
For MSP ticket automation via Discord
