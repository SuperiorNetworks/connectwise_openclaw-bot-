# Quick Start: Discord Ticket Bot for Your MSP

This bot makes it easy to create and update service tickets in ConnectWise right from Discord—no forms, no portals, just chat.

## Getting Started (5 minutes)

### Step 1: Join the Ticket Channel

Your MSP will add your team to the `#cw-ticketing` Discord channel. That's where the bot lives.

### Step 2: Create Your First Ticket

Just type a client name:

```
Your Client Name
```

The bot will walk you through the rest:

```
Bot: 📋 Subject for Your Client Name?
You: Server down
Bot: 📝 Description/Details?
You: Main server offline, users can't access files
Bot: ⏱️ Time to log? (or 'skip')
You: 2 hours
Bot: ✅ Ticket #31642 Created
```

That's it. Your ticket is in ConnectWise.

## Common Tasks

### Create a Ticket

**Start with a client name:**
```
Your Client Name
```

**Answer 4 questions:**
1. What's the subject? (one line)
2. What's the problem & what did you do? (few sentences)
3. How long did it take? (hours, or "skip")

### Add Notes to an Existing Ticket

**Start with a ticket number:**
```
#31641
```

**Add your note:**
```
Followed up with client; all systems stable
```

**Log time (optional):**
```
30 minutes
```

### Switch Between Tickets

At any point in a conversation, you can switch:
- Start a **new ticket**: `new ticket for Client Name`
- **Update a different ticket**: `#31580`

## Writing Your Notes

Keep it clear and direct:

✅ **Good:**
```
• Server was offline
• I rebooted it and checked diagnostics
• Everything's working now
```

❌ **Bad:**
```
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

## What Happens After You Submit?

1. **Ticket is created** in ConnectWise automatically
2. **Time is logged** (if you included hours)
3. **Bot sends you a link** to view the ticket
4. **Your MSP can see it immediately** and assign it if needed

## Pro Tips

- **Be specific**: "Fiber modem rebooted" beats "network issue fixed"
- **Include context**: Why did you do it? (helps future techs)
- **One ticket per issue**: Don't combine unrelated problems
- **Skip time if internal**: Only log time for billable work

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
