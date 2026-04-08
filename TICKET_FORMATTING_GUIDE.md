# Ticket Formatting Guide for Service Technicians

This guide explains how to write ConnectWise service tickets using the Discord Conversational Ticket Bot, following Superior Networks' ticket writing standards.

## Overview

The bot guides you through ticket creation step-by-step. This document explains the **formatting rules** for the ticket content itself.

## Ticket Structure

Every ticket follows this format:

```
SUMMARY (11 words or less)

PROBLEM / DESCRIPTION & RESOLUTION (3–4 bullet points)

WORK ROLE: [Role Name]
TAXABLE: [Yes / No]
```

## Rules

### 1. Summary (11 words maximum)

- Keep it short, specific, and searchable
- Describes the work performed or issue resolved
- No jargon unless necessary
- Examples:
  - ✅ "Server reboot and disk space diagnostics completed"
  - ✅ "Wi-Fi access point firmware updated"
  - ✅ "User password reset and training provided"
  - ❌ "Stuff fixed" (too vague)
  - ❌ "Performed comprehensive system infrastructure optimization analysis" (too long, wordy)

### 2. Problem / Description & Resolution (3–4 bullets)

Use **3–4 bullet points** covering:
1. **What was wrong** (the problem)
2. **What you did** (the action)
3. **What happened** (the outcome)
4. (Optional) **Why it matters** (context)

#### Style Rules:
- Write like a working technician, not a robot
- Use casual punctuation where it fits
- Be direct and clear
- Include specific software/hardware names
- Provide context useful for future reference
- Keep each bullet 1–2 sentences max

#### Examples:

✅ **Good Example:**
```
• Main file server was offline; users couldn't access shared drives
• Rebooted server and ran hardware diagnostics; no errors found
• Server back online; all shares remounted; users have access
• Checked logs — graceful shutdown, likely power spike
```

✅ **Good Example:**
```
• Ubiquiti UniFi access point losing connection every 4 hours
• Updated firmware from v5.43 to v6.12; cleared config cache
• AP now stable; no disconnects in 48h testing
• Client using PoE injector (non-UPS); might need power conditioning
```

✅ **Good Example:**
```
• End-user locked out of email; forgot password; couldn't reset
• Reset password in AD; synced to Office 365; tested login
• User back online; confirmed Outlook and webmail both working
```

❌ **Bad Example:**
```
• Did some work on the thing
• It's better now
```

❌ **Bad Example:**
```
• Extended comprehensive system diagnostic procedures utilizing industry-standard methodologies
• Implemented multi-layer infrastructure optimization strategies
• Achieved enhanced operational capacity metrics
```

### 3. Work Role & Taxable Status

After the bullet points, indicate the **work role** and whether it's **taxable** for billing purposes.

**Format:**
```
WORK ROLE: [Role Name]
TAXABLE: [Yes / No]
```

#### Work Roles (Choose one):

| Work Role | Taxable? | When to Use |
| Hardware Installation & Configuration | Yes | Installing new servers, switches, access points; configuring hardware settings |
| Hardware Repair & Maintenance | Yes | Replacing hard drives, reseating cables, troubleshooting physical issues |
| Software Deployment & Configuration | No | Installing software, patching, configuration changes |
| IT Consulting & Advisory Services | No | Planning, recommendations, strategy discussions |
| End-User Training & Onboarding | No | Teaching users, documentation, training sessions |
| Managed Services & Remote Monitoring | No | Routine monitoring, maintenance, proactive support |

#### Examples:

✅ **Hardware Installation:**
```
WORK ROLE: Hardware Installation & Configuration
TAXABLE: Yes
```

✅ **Software Patch:**
```
WORK ROLE: Software Deployment & Configuration
TAXABLE: No
```

✅ **User Training:**
```
WORK ROLE: End-User Training & Onboarding
TAXABLE: No
```

## Using the Discord Bot

### Create a New Ticket

The bot will ask you for:

1. **Client/Company** — Type the client name (e.g., "Client A")
2. **Subject** — What's this ticket about?
3. **Description** — What was the problem and how did you fix it?
4. **Time** — How many hours did you spend? (or "skip")

**Example conversation:**

```
You: Client A
Bot: 📋 Subject for Client A?

You: Server reboot and disk space diagnostics completed
Bot: 📝 Description/Details?

You:
• Main file server was offline; users couldn't access shared drives
• Rebooted server and ran hardware diagnostics; no errors found
• Server back online; all shares remounted; users have access
• Checked logs — graceful shutdown, likely power spike

WORK ROLE: Hardware Repair & Maintenance
TAXABLE: Yes

Bot: ⏱️ Time to log? (or 'skip')

You: 2 hours
Bot: ✅ Ticket #31642 Created
```

### Update an Existing Ticket

If you want to add a note to an existing ticket:

```
You: #31641
Bot: 📝 Note to add?

You: Followed up with client; confirmed no further issues. System stable 24 hours.
Bot: ⏱️ Time to log? (or 'skip')

You: 30 minutes
Bot: ✅ Note Added to Ticket #31641
```

## Common Scenarios

### Scenario 1: Hardware Replacement

```
Summary: Hard drive replaced on production server

• Server showing S.M.A.R.T. errors on C: drive; performance degraded
• Replaced 2TB SSD (Samsung 870 EVO); cloned data from backup
• Server rebuilt; tested full restore; all systems online
• Scheduled follow-up monitoring for 48 hours

WORK ROLE: Hardware Repair & Maintenance
TAXABLE: Yes
```

### Scenario 2: Software Update

```
Summary: Microsoft Office patched across client workstations

• Client machines missing critical security updates; audit flagged vulnerabilities
• Deployed Microsoft Office 2021 cumulative patch (KB5023061) via WSUS
• 47 machines patched successfully; 2 required manual intervention
• All machines validated post-patch; no compatibility issues detected

WORK ROLE: Software Deployment & Configuration
TAXABLE: No
```

### Scenario 3: User Support

```
Summary: End-user trained on new email migration process

• Client migrating from on-prem Exchange to Microsoft 365
• Conducted 1:1 training session; covered Outlook setup, folder migration, calendar sync
• User comfortable with new system; data successfully migrated
• Sent documentation for reference; available for follow-up questions

WORK ROLE: End-User Training & Onboarding
TAXABLE: No
```

### Scenario 4: Consulting

```
Summary: Network infrastructure assessment and upgrade recommendation

• Client experiencing bandwidth bottlenecks during peak hours; switches aging
• Conducted site survey; mapped current topology; tested throughput
• Recommended upgrade path: new core switches (Cisco Catalyst 9300) + fiber backhaul
• Provided cost analysis and 6-month implementation timeline

WORK ROLE: IT Consulting & Advisory Services
TAXABLE: No
```

## Tips for Writing Good Tickets

### ✅ DO:
- Be specific about hardware/software versions
- Mention client names where relevant
- Include "why it matters" context for future techs
- Write like you're explaining to a coworker
- Use short, direct sentences
- Include specific error codes or symptoms if applicable

### ❌ DON'T:
- Use filler phrases ("went ahead and", "touched base on")
- Write like a corporate memo
- Include labor rates or billing details
- Add multiple "Additional Notes" sections
- Ramble or over-explain
- Use vague terms ("system" instead of server/workstation/network)

## Priority & Time Notation

The bot supports automatic priority detection and flexible time input:

### Priority Keywords:
- **critical** or **p1** → Critical
- **high** or **p2** → High
- **medium** or **p3** → Medium (default)
- **low** or **p4** → Low

Include priority keywords in your description if needed. If not specified, defaults to Medium.

### Time Input Formats:
- `5 hours` → 5.0
- `2.5 hrs` → 2.5
- `30 minutes` → 0.5
- `90 mins` → 1.5

## Questions?

If a ticket doesn't fit the standard format, ask yourself:
- **Is it a creation or an update?** (Bot handles both)
- **Do I have the client name?** (Required for new tickets)
- **Can I describe it in 3–4 bullets?** (Required for all tickets)
- **What's the primary work role?** (Required for categorization)

Otherwise, just start typing and the bot will guide you.

---

**Last Updated:** April 8, 2026  
**Version:** 1.0.0
