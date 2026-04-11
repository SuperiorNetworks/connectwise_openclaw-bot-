"""
Discord Conversational Ticket Bot Module v2 - Enhanced Parsing & Scheduling

This module extends the core bot with:
- One-shot prompt parsing (extract all info from single message)
- Calendar scheduling integration
- Natural language date/time parsing
- Smarter context extraction

Core Features:
  - Parse "Create ticket for [Client] with subject [...], description [...], schedule [date/time]"
  - Auto-schedule appointments in ConnectWise
  - Extract structured data from free-form text
  - Fall back to conversational flow if parsing incomplete

Input:
  - Discord bot instance
  - ConnectWise API credentials (via config)
  - User messages (Discord channel)

Output:
  - Created/updated tickets in ConnectWise
  - Scheduled appointments (calendar entries)
  - Discord confirmation embeds with links

Dependencies:
  - discord.py 2.3.2+
  - requests
  - dateutil (for natural language date parsing)
  - re, base64, lzma, json

Change Log:
  2026-04-09 v2.0.0 - Enhanced parsing, scheduling, and natural language support
  2026-04-11 v2.0.1 - Fixed update detection: now matches 'add to ticket N', 'note on N', bare '#N' (Dwain Henderson Jr)
  2026-04-11 v2.0.2 - Fixed 400 error on note POST: detailDescriptionFlag must be True (Dwain Henderson Jr)
  2026-04-11 v2.0.3 - Auto-bullet multi-line notes; strip formatting instructions like 'list in bullet style' (Dwain Henderson Jr)
"""

import re
import json
import base64
import lzma
import requests
from datetime import datetime, timedelta, time, time
from typing import Optional, Tuple, Dict, Any
try:
    from dateutil.parser import parse as parse_date
    from dateutil.relativedelta import relativedelta
except ImportError:
    parse_date = None
    relativedelta = None
import discord
from discord.ext import commands


class DiscordTicketBotV2Enhanced(commands.Cog):
    """Enhanced ticket bot with one-shot parsing and scheduling"""
    
    def __init__(self, bot: commands.Bot, config: Dict[str, Any]):
        self.bot = bot
        self.config = config
        self.channel_id = int(config.get("discord_channel_id", 0))
        self.guild_id = config.get("discord_guild_id")
        
        # CW API config
        self.cw_base_url = config.get("cw_base_url", "https://na.myconnectwise.net/v4_6_release/apis/3.0")
        self.cw_company = config.get("cw_company")
        self.cw_public_key = config.get("cw_public_key")
        self.cw_private_key = config.get("cw_private_key")
        self.cw_client_id = config.get("cw_client_id")
        self.cw_member_id = config.get("cw_member_id")
        
        self.company_mapping = config.get("company_mapping", {})
        self.priority_ids = config.get("priority_ids", {})
        self.default_priority_id = config.get("default_priority_id", 8)
        
        # Conversation state
        self.conversations = {}
    
    # ============================================================================
    # ENHANCED PARSING - One-shot extraction
    # ============================================================================
    
    def parse_full_ticket_request(self, text: str) -> Dict[str, Any]:
        """
        Parse a complete ticket request from a single message.
        
        Returns dict with extracted fields:
        {
            "client_name": "Positive Electric",
            "subject": "...",
            "description": "...",
            "hours": 4,
            "schedule_date": datetime,
            "schedule_time": time,
            "priority": "medium",
            "complete": bool  # True if all required fields found
        }
        """
        result = {
            "client_name": None,
            "subject": None,
            "description": None,
            "hours": None,
            "schedule_date": None,
            "schedule_time": None,
            "priority": None,
            "complete": False,
            "note_body": None
        }
        
        # Extract client name
        client_name = self._extract_client_name(text)
        if client_name:
            result["client_name"] = client_name
        
        # Extract subject (first sentence, or after "subject:" keyword)
        subject = self._extract_subject(text)
        if subject:
            result["subject"] = subject
        
        # Extract description (multiple sentences after subject)
        description = self._extract_description(text)
        if description:
            result["description"] = description
        
        # Extract hours/time worked
        hours = self._extract_hours(text)
        if hours:
            result["hours"] = hours
        
        # Extract scheduled date/time
        schedule_dt = self._extract_schedule_datetime(text)
        if schedule_dt:
            result["schedule_date"] = schedule_dt.date()
            result["schedule_time"] = schedule_dt.time()
        
        # Extract priority
        priority = self._extract_priority(text)
        if priority:
            result["priority"] = priority
        
        # Check if we have minimum required fields
        note_body = self._extract_note_body(text)
        if note_body:
            result["note_body"] = note_body
        # Ticket is complete with just client + subject (description is optional)
        result["complete"] = bool(result["client_name"] and result["subject"])
        
        return result
    
    def _extract_client_name(self, text: str) -> Optional[str]:
        """Extract client name from text"""
        # Look for exact matches first
        for company_name in self.company_mapping.keys():
            if re.search(rf'\b{re.escape(company_name)}\b', text, re.IGNORECASE):
                return company_name
        
        # Fuzzy match if no exact match
        words = text.split()
        for company_name in self.company_mapping.keys():
            company_words = company_name.lower().split()
            if any(word.lower() in [w.lower() for w in words] for word in company_words):
                return company_name
        
        return None
    
    def _extract_subject(self, text: str) -> Optional[str]:
        """Extract subject (usually first meaningful sentence)"""
        # Look for "subject:" keyword
        match = re.search(r'(?:summary|title|subject)\s*:\s*([^\n]+)', text, re.IGNORECASE)
        if match:
            return match.group(1).strip()

        # Strip lead-in phrases like "make a X ticket", "create a ticket for X"
        clean = re.sub(r'(?i)^(make|create|open|log|submit|add|new)\s+(a\s+|an\s+)?[\w\s]+?ticket\.?\s*', '', text).strip()
        clean = re.sub(r'(?i)^(create|open|log|submit)\s+(a\s+|an\s+)?new\s+ticket\s+(for\s+[\w\s]+?)?[.:]?\s*', '', clean).strip()

        # Strip client name from start
        client = self._extract_client_name(text)
        if client and clean.lower().startswith(client.lower()):
            clean = clean[len(client):].lstrip(', .')

        # Expanded verb list covering IT tasks
        verbs = ('hang|mount|install|replace|repair|upgrade|configure|setup|troubleshoot|diagnose'
                 '|reformat|format|rebuild|migrate|move|add|remove|delete|update|patch|fix|restore'
                 '|backup|deploy|provision|connect|disconnect|reset|image|wipe|clone|transfer'
                 '|set up|put|send|check|review|audit|test|verify|enable|disable')
        match = re.search(r'(' + verbs + r')[^.!?\n]+', clean, re.IGNORECASE)
        if match:
            sentence = match.group(0).strip()
            words = sentence.split()
            if len(words) > 15:
                sentence = " ".join(words[:15])
            return sentence

        # Final fallback: use first sentence of cleaned text
        first_sentence = re.split(r'[.!?\n]', clean)[0].strip()
        if len(first_sentence) > 5:
            words = first_sentence.split()
            if len(words) > 15:
                first_sentence = " ".join(words[:15])
            return first_sentence

        return None
    
    def _extract_description(self, text: str) -> Optional[str]:
        """Extract description (remaining details)"""
        # Remove the subject from text
        subject = self._extract_subject(text)
        if subject:
            text = text.replace(subject, "", 1)
        
        # Extract meaningful lines (skip dates/times)
        lines = text.split('\n')
        description_lines = []
        
        for line in lines:
            line = line.strip()
            # Skip empty, very short, or date/time patterns
            if line and len(line) > 10 and not re.match(r'(thursday|monday|tuesday|wednesday|friday|saturday|sunday|\d{1,2}:\d{2}|am|pm)', line, re.IGNORECASE):
                description_lines.append(f"• {line}")
        
        if description_lines:
            return "\n".join(description_lines[:4])  # Max 4 bullets
        
        return None
    

    def _extract_note_body(self, text):
        """Extract body text to post as a ticket note (everything after Summary:/Title: line)"""
        # If there is a Summary:/Title: label, everything after that line is the note body
        m = re.search(
            r'(?:summary|title|subject)\s*:\s*[^\n]+\n(.*)',
            text, re.IGNORECASE | re.DOTALL
        )
        if m:
            body = m.group(1).strip()
            if body:
                return body
        # Otherwise: everything after the subject sentence is the note body
        subject = self._extract_subject(text)
        if subject:
            idx = text.lower().find(subject.lower())
            if idx >= 0:
                after = text[idx + len(subject):].strip().lstrip('.!?,;:\n ')
                client = self._extract_client_name(text)
                if client:
                    after = re.sub(re.escape(client), '', after, flags=re.IGNORECASE).strip()
                after = re.sub(
                    r'(?i)^(make|create|open|log|submit)\s+(a\s+)?[\w\s]+?ticket\.?\s*',
                    '', after
                ).strip()
                if len(after) > 5:
                    return after
        return None

    def _extract_hours(self, text: str) -> Optional[float]:
        """Extract hours worked"""
        # Match patterns like "4 hours", "2.5 hrs", "30 minutes", etc.
        match = re.search(r'(\d+(?:\.\d+)?)\s*(hours?|hrs?|h|minutes?|mins?)', text, re.IGNORECASE)
        if match:
            value = float(match.group(1))
            unit = match.group(2).lower()
            
            if 'min' in unit:
                return value / 60
            return value
        
        return None
    
    def _extract_schedule_datetime(self, text: str) -> Optional[datetime]:
        """Extract scheduled date and time"""
        # Look for day names (Thursday, Friday, etc.)
        day_pattern = r'\b(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b'
        day_match = re.search(day_pattern, text, re.IGNORECASE)
        
        if not day_match:
            return None
        
        day_name = day_match.group(1).lower()
        
        # Look for time pattern (9 am, 9:00 AM, 14:30, etc.)
        # IMPORTANT: Require AM/PM for single-digit hours to avoid matching product numbers like "24-port"
        time_pattern = r'(?:(\d{1,2}):(\d{2})|(\d{1,2})\s+(am|pm|a\.m|p\.m))'
        time_match = re.search(time_pattern, text, re.IGNORECASE)
        
        if not time_match:
            return None
        
        # Regex has 4 groups: (1) HH from HH:MM, (2) MM from HH:MM, (3) hour from "N am/pm", (4) am/pm
        # Either groups 1+2 match (HH:MM format) OR groups 3+4 match ("N am/pm" format)
        if time_match.group(1):  # HH:MM format matched
            hour = int(time_match.group(1))
            minute = int(time_match.group(2))
            ampm = None
        else:  # "N am/pm" format matched
            hour = int(time_match.group(3))
            minute = 0
            ampm = time_match.group(4)
        
        # Convert to 24-hour if AM/PM specified
        if ampm:
            if 'p' in ampm.lower() and hour < 12:
                hour += 12
            elif 'a' in ampm.lower() and hour == 12:
                hour = 0
        
        # Find the next occurrence of the day
        days = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
        day_index = days.index(day_name)
        today = datetime.now().replace(hour=hour, minute=minute, second=0, microsecond=0)
        today_index = today.weekday()
        
        days_ahead = day_index - today_index
        if days_ahead < 0:  # Target day already happened this week
            days_ahead += 7
        elif days_ahead == 0 and today.time() < time(hour, minute):
            # Same day but time hasn't passed yet
            pass
        elif days_ahead == 0:
            # Same day but time already passed
            days_ahead = 7
        
        return today + timedelta(days=days_ahead)
    
    def _extract_priority(self, text: str) -> Optional[str]:
        """Extract priority level"""
        priority_keywords = {
            r'\b(critical|emergency|urgent|p1)\b': 'critical',
            r'\b(high|p2)\b': 'high',
            r'\b(medium|p3|standard)\b': 'medium',
            r'\b(low|p4|minor)\b': 'low'
        }
        
        for pattern, priority in priority_keywords.items():
            if re.search(pattern, text, re.IGNORECASE):
                return priority
        
        return None
    
    # ============================================================================
    # CONNECTWISE API - Ticket & Schedule Creation
    # ============================================================================
    
    def create_ticket(self, company_id: int, subject: str, description: str, 
                     priority_id: int, priority_name: str) -> Dict[str, Any]:
        """Create a ticket in ConnectWise"""
        auth = base64.b64encode(
            f"{self.cw_company}+{self.cw_public_key}:{self.cw_private_key}".encode()
        ).decode()
        
        headers = {
            "Authorization": f"Basic {auth}",
            "clientId": self.cw_client_id,
            "Accept": "application/json",
            "Content-Type": "application/json"
        }
        
        payload = {
            "company": {"id": company_id},
            "summary": subject[:200],
            "initialDescription": description,
            "priority": {"id": priority_id}
        }
        
        try:
            resp = requests.post(
                f"{self.cw_base_url}/service/tickets",
                headers=headers,
                json=payload,
                timeout=10
            )
            resp.raise_for_status()
            ticket_data = resp.json()
            
            return {
                "status": "success",
                "ticket_id": ticket_data.get("id"),
                "ticket_num": ticket_data.get("ticketNumber") or ticket_data.get("id"),
                "cw_link": self._generate_deep_link(ticket_data.get("id"))
            }
        except Exception as e:
            return {
                "status": "error",
                "error": str(e)
            }
    
    def create_schedule_entry(self, ticket_id: int, date: datetime.date, 
                             time_obj: datetime.time) -> Dict[str, Any]:
        """Schedule an appointment in ConnectWise"""
        auth = base64.b64encode(
            f"{self.cw_company}+{self.cw_public_key}:{self.cw_private_key}".encode()
        ).decode()
        
        headers = {
            "Authorization": f"Basic {auth}",
            "clientId": self.cw_client_id,
            "Accept": "application/json",
            "Content-Type": "application/json"
        }
        
        # Convert to UTC (assuming local time input)
        # This is a simplification; you may need timezone handling
        start_dt = datetime.combine(date, time_obj)
        end_dt = start_dt + timedelta(hours=2)  # Default 2-hour appointment
        
        payload = {
            "objectId": ticket_id,
            "type": {"id": 4},  # Service ticket
            "member": {"id": self.cw_member_id},
            "dateStart": start_dt.isoformat() + "Z",
            "dateEnd": end_dt.isoformat() + "Z",
            "status": {"id": 2}  # Firm (scheduled)
        }
        
        try:
            resp = requests.post(
                f"{self.cw_base_url}/schedule/entries",
                headers=headers,
                json=payload,
                timeout=10
            )
            resp.raise_for_status()
            schedule_data = resp.json()
            
            return {
                "status": "success",
                "schedule_id": schedule_data.get("id"),
                "scheduled_time": f"{date} @ {time_obj.strftime('%H:%M')}"
            }
        except Exception as e:
            return {
                "status": "error",
                "error": str(e)
            }
    

    def upload_image_to_ticket(self, ticket_id: int, image_url: str, filename: str = None) -> dict:
        """Download a Discord image and upload it to ConnectWise as an inline ticket document.
        Replicates the behavior of pasting a screenshot into the CW discussion editor."""
        import requests as _req, io as _io, os as _os
        auth = __import__('base64').b64encode(
            f"{self.cw_company}+{self.cw_public_key}:{self.cw_private_key}".encode()
        ).decode()
        headers_auth = {
            "Authorization": f"Basic {auth}",
            "clientId": self.cw_client_id,
        }
        try:
            img_resp = _req.get(image_url, timeout=30)
            img_resp.raise_for_status()
            img_data = img_resp.content
            content_type = img_resp.headers.get('Content-Type', 'image/png')
            if not filename:
                filename = _os.path.basename(image_url.split('?')[0]) or 'attachment.png'
            files = {'file': (filename, _io.BytesIO(img_data), content_type)}
            data = {
                'recordType': 'Ticket',
                'recordId': str(ticket_id),
                'title': filename,
                'isPublic': 'true',
            }
            upload_resp = _req.post(
                f"{self.cw_base_url}/system/documents",
                headers=headers_auth,
                files=files,
                data=data,
                timeout=30
            )
            upload_resp.raise_for_status()
            doc = upload_resp.json()
            doc_id = doc.get('id')
            print(f"  [image] Uploaded {filename} -> CW document #{doc_id} on ticket #{ticket_id}")
            return {"status": "success", "doc_id": doc_id, "filename": filename}
        except Exception as e:
            print(f"  [image] Upload failed for {image_url}: {e}")
            return {"status": "error", "error": str(e)}

    def update_ticket(self, ticket_id: int, note: str, member_id: str = None) -> dict:
        """Add a note/update to an existing ConnectWise ticket"""
        auth = __import__('base64').b64encode(
            f"{self.cw_company}+{self.cw_public_key}:{self.cw_private_key}".encode()
        ).decode()

        headers = {
            "Authorization": f"Basic {auth}",
            "clientId": self.cw_client_id,
            "Accept": "application/json",
            "Content-Type": "application/json"
        }

        payload = {
            "text": note,
            "detailDescriptionFlag": True,   # REQUIRED: at least one flag must be True
            "internalAnalysisFlag": False,
            "resolutionFlag": False
        }
        if member_id:
            payload["member"] = {"identifier": member_id}

        try:
            resp = __import__('requests').post(
                f"{self.cw_base_url}/service/tickets/{ticket_id}/notes",
                headers=headers,
                json=payload,
                timeout=10
            )
            resp.raise_for_status()
            note_data = resp.json()
            return {"status": "success", "note_id": note_data.get("id")}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def get_ticket(self, ticket_id: int) -> dict:
        """Fetch a ConnectWise ticket by ID"""
        auth = __import__('base64').b64encode(
            f"{self.cw_company}+{self.cw_public_key}:{self.cw_private_key}".encode()
        ).decode()

        headers = {
            "Authorization": f"Basic {auth}",
            "clientId": self.cw_client_id,
            "Accept": "application/json"
        }

        try:
            resp = __import__('requests').get(
                f"{self.cw_base_url}/service/tickets/{ticket_id}",
                headers=headers,
                timeout=10
            )
            resp.raise_for_status()
            return {"status": "success", "ticket": resp.json()}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def _generate_deep_link(self, ticket_id: int) -> str:
        """Generate ConnectWise direct ticket link"""
        return f"https://na.myconnectwise.net/v4_6_release/services/system_io/Service/fv_sr100_request.rails?service_recid={ticket_id}&companyName=superiornet"


    # ============================================================================
    # MESSAGE HANDLING
    # ============================================================================
    
    async def handle_ticket_request(self, message: discord.Message, text: str):
        """Try to parse and handle a complete ticket request"""
        # Check for update/note ticket command first
        # Matches: update ticket 31666, add to ticket 31666, note on ticket 31666,
        #          add note to ticket 31666, #31666, ticket 31666 - <note>
        update_match = re.search(
            r'(?i)(?:update|add(?:\s+(?:a\s+)?note)?(?:\s+to)?|note(?:\s+on)?(?:\s+to)?)\s+ticket\s+#?(\d{4,6})\b',
            text
        )
        if not update_match:
            # Also match bare '#31666' or 'ticket 31666' at start/anywhere
            update_match = re.search(r'(?i)\bticket\s+#?(\d{4,6})\b', text)
        if not update_match:
            update_match = re.search(r'#(\d{4,6})\b', text)
        if update_match:
            ticket_id = int(update_match.group(1))
            # Strip the ticket reference prefix to get the note text
            note_text = re.sub(
                r'(?i)(?:update|add(?:\s+(?:a\s+)?note)?(?:\s+to)?|note(?:\s+on)?(?:\s+to)?)\s+ticket\s+#?\d{4,6}\s*[-:\s]*',
                '', text
            ).strip()
            # Also strip bare 'ticket NNNNN' or '#NNNNN' prefix if note_text still equals original
            if not note_text or note_text == text:
                note_text = re.sub(r'(?i)\bticket\s+#?\d{4,6}\s*[-:\s]*', '', text).strip()
            if not note_text or note_text == text:
                note_text = re.sub(r'#\d{4,6}\s*[-:\s]*', '', text).strip()
            await self._handle_ticket_update(message, ticket_id, note_text)
            return

        parsed = self.parse_full_ticket_request(text)
        
        if not parsed["client_name"]:
            await message.reply("❌ Start with a client name (e.g., 'Positive Electric')")
            return
        
        # If complete, create ticket + schedule
        if parsed["complete"]:
            await self._create_ticket_and_schedule(message, parsed)
        else:
            # Fall back to conversational flow
            await self._start_conversational_flow(message, parsed)

    def _format_note(self, note: str) -> str:
        """Format note text: strip formatting instructions and auto-bullet multi-line notes."""
        # Detect and remove any line that says 'list in bullet style' (case-insensitive, anywhere)
        bullet_instruction = re.search(
            r'(?im)^\s*list\s+(?:it\s+)?in\s+bullet(?:\s+style|s)?\.?\s*$', note
        )
        wants_bullets = bool(bullet_instruction)
        if bullet_instruction:
            note = (note[:bullet_instruction.start()] + note[bullet_instruction.end():]).strip()

        # Split into non-empty lines
        lines = [ln.strip() for ln in note.splitlines() if ln.strip()]

        if len(lines) <= 1:
            return note  # Single line — no formatting needed

        # Multi-line: always format as bullet list (whether or not instruction was given)
        return '\n'.join(f'• {ln}' for ln in lines)

    async def _handle_ticket_update(self, message: discord.Message, ticket_id: int, note: str):
        """Add a note to an existing ConnectWise ticket"""
        if not note:
            await message.reply(f"📝 What update should I add to ticket #{ticket_id}?")
            # Store in conversation state waiting for note text
            self.conversations[message.author.id] = {
                "mode": "update",
                "stage": "note",
                "data": {"ticket_id": ticket_id}
            }
            return

        # Fetch ticket to confirm it exists and get client name
        ticket_result = self.get_ticket(ticket_id)
        if ticket_result["status"] != "success":
            await message.reply(f"❌ Ticket #{ticket_id} not found in ConnectWise")
            return

        ticket = ticket_result["ticket"]
        company_name = ticket.get("company", {}).get("name", "Unknown")
        summary = ticket.get("summary", "")

        # Format note: auto-bullet multi-line notes, strip formatting instructions
        note = self._format_note(note)
        # Append Discord image/file attachments to the note
        if message.attachments:
            att_lines = [f"[Attachment from {message.author.name}]: {att.url}" for att in message.attachments]
            note = (note + "\n\n" + "\n".join(att_lines)).strip()
        # Post the note
        update_result = self.update_ticket(ticket_id, note)
        if update_result["status"] != "success":
            await message.reply(f"❌ Failed to update ticket: {update_result.get('error')}")
            return

        embed = discord.Embed(
            title=f"✅ Ticket #{ticket_id} Updated",
            description=summary,
            color=discord.Color.blue(),
            url=self._generate_deep_link(ticket_id)
        )
        embed.add_field(name="Client", value=company_name, inline=True)
        embed.add_field(name="Note Added", value=note[:500], inline=False)
        embed.add_field(name="Link", value=f"[Open in ConnectWise]({self._generate_deep_link(ticket_id)})", inline=False)
        embed.set_footer(text=f"Updated by {message.author.name}")

        await message.reply(embed=embed, mention_author=False)
        print(f"✅ Updated ticket #{ticket_id} with note")
    
    async def _create_ticket_and_schedule(self, message: discord.Message, parsed: Dict[str, Any]):
        """Create ticket and optionally schedule appointment"""
        company_id = self.company_mapping.get(parsed["client_name"])
        if not company_id:
            await message.reply(f"❌ Client '{parsed['client_name']}' not found in mapping")
            return
        
        # Determine priority
        priority_name = parsed["priority"] or "medium"
        priority_id = self.priority_ids.get(priority_name, self.default_priority_id)
        
        # Create ticket
        ticket_result = self.create_ticket(
            company_id,
            parsed["subject"],
            parsed["description"],
            priority_id,
            priority_name
        )
        
        if ticket_result["status"] != "success":
            await message.reply(f"❌ Failed to create ticket: {ticket_result.get('error')}")
            return
        
        ticket_id = ticket_result["ticket_id"]
        
        # Build response embed
        embed = discord.Embed(
            title=f"✅ Ticket #{ticket_result['ticket_num']} Created",
            description=re.sub(r"^[:\s,.|]+", "", parsed["subject"]).strip() if parsed["subject"] else "",
            color=discord.Color.green(),
            url=ticket_result["cw_link"]
        )
        embed.add_field(name="Client", value=parsed["client_name"], inline=True)
        embed.add_field(name="Priority", value=priority_name.capitalize(), inline=True)
        
        if parsed["hours"]:
            embed.add_field(name="Hours Logged", value=f"{parsed['hours']} hrs", inline=True)
        
        # Schedule if date/time provided
        if parsed["schedule_date"] and parsed["schedule_time"]:
            schedule_result = self.create_schedule_entry(ticket_id, parsed["schedule_date"], parsed["schedule_time"])
            
            if schedule_result["status"] == "success":
                embed.add_field(
                    name="📅 Scheduled",
                    value=schedule_result["scheduled_time"],
                    inline=False
                )
            else:
                embed.add_field(
                    name="⚠️ Scheduling Failed",
                    value=schedule_result.get("error"),
                    inline=False
                )
        
        embed.add_field(name="Link", value=f"[Open in ConnectWise]({ticket_result['cw_link']})", inline=False)
        embed.set_footer(text=f"Created by {message.author.name}")
        
        await message.reply(embed=embed, mention_author=False)
        print(f"✅ Created ticket #{ticket_result['ticket_num']} with schedule")
        # Post note body as text, then upload images as inline CW documents
        note_parts = []
        if parsed.get("note_body"):
            note_parts.append(parsed["note_body"])
        if note_parts:
            self.update_ticket(ticket_id, '\n\n'.join(note_parts))
            print(f"  Note posted to ticket #{ticket_result['ticket_num']}")
        if message.attachments:
            for att in message.attachments:
                self.upload_image_to_ticket(ticket_id, att.url, att.filename)
    
    async def _start_conversational_flow(self, message: discord.Message, parsed: Dict[str, Any]):
        """Fall back to conversational flow if info is incomplete"""
        user_id = message.author.id
        
        self.conversations[user_id] = {
            "mode": "create",
            "stage": "subject" if not parsed["subject"] else ("description" if not parsed["description"] else "time"),
            "data": {
                "company_id": self.company_mapping.get(parsed["client_name"]),
                "company_name": parsed["client_name"],
                "subject": parsed["subject"],
                "description": parsed["description"],
                "hours": parsed["hours"],
                "schedule_date": parsed["schedule_date"],
                "schedule_time": parsed["schedule_time"]
            }
        }
        
        # Ask for missing field
        if not parsed["subject"]:
            await message.reply(f"📋 Subject for {parsed['client_name']}?")
        elif not parsed["description"]:
            await message.reply("📝 Description/Details?")
        else:
            await message.reply("⏱️ Time to log? (or 'skip')")
    
    @commands.Cog.listener()
    async def on_ready(self):
        """Bot ready"""
        print(f"✅ Enhanced Bot v2 logged in as {self.bot.user}")
    
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Main message listener"""
        if message.author == self.bot.user or message.channel.id != self.channel_id:
            return
        
        print(f"\n[{datetime.now().isoformat()}] {message.author}: {message.content[:80]}")
        
        user_id = message.author.id
        content = message.content.strip()
        
        # Try enhanced parsing first (one-shot)
        if user_id not in self.conversations:
            await self.handle_ticket_request(message, content)
        else:
            conv = self.conversations[user_id]
            # Handle update note stage
            if conv.get("mode") == "update" and conv.get("stage") == "note":
                ticket_id = conv["data"]["ticket_id"]
                del self.conversations[user_id]
                await self._handle_ticket_update(message, ticket_id, content)
            else:
                # Handle conversational create flow
                print(f"In active conversation (continuing flow)")


def setup(bot: commands.Bot, config: Dict[str, Any]):
    """Load cog into bot"""
    bot.add_cog(DiscordTicketBotV2Enhanced(bot, config))
