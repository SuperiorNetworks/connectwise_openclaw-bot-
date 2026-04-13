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
  2026-04-11 v2.0.4 - Added Miles:/AI: command prefix system with Claude AI routing (Dwain Henderson Jr)
  2026-04-11 v2.0.5 - Fixed conversational fallback: bare client name no longer treated as subject (Dwain Henderson Jr)
  2026-04-11 v2.0.6 - Fixed silent conversation handler (subject/description/time stages now respond); fixed fuzzy client match stopword filter; added cancel/stop command (Dwain Henderson Jr)
  2026-04-11 v2.0.7 - Fixed bare ticket number detection (e.g. 'add these labels 31671'); extended file upload to support PDFs and all attachment types (Dwain Henderson Jr)
  2026-04-11 v2.0.8 - Fixed attachment upload on ticket updates: files now uploaded to CW instead of appended as URL text (Dwain Henderson Jr)
  2026-04-11 v2.0.9 - Added log_time() API method; time range parser (HH:MM - HH:MM); update flow now creates CW time entry and asks for time if not provided (Dwain Henderson Jr)
  2026-04-12 v2.1.0 - Live ConnectWise company sync: pulls full client list on startup, auto-refreshes every 24 hours as background task, manual refresh via 'Miles: refresh clients' command (Dwain Henderson Jr)
  2026-04-12 v2.5.0 - Dual-mode: #cw-ticketing is CW-only; DMs and @mentions use full conversational assistant with persistent memory (Claude Haiku) (Dwain Henderson Jr)
  2026-04-13 v2.6.0 - Added dedicated assistant channels (e.g. #nyc-2026): Miles responds to ALL messages in these channels without requiring @mention (Dwain Henderson Jr)
  2026-04-13 v2.7.0 - Added image vision support in assistant mode: Miles can now read images/screenshots attached to messages in DMs, #nyc-2026, and @mention channels (Dwain Henderson Jr)
  2026-04-13 v2.7.1 - Fixed work role on time entries: bot now extracts 'Work Role:' line from Discord note, fuzzy-matches it to CW work role list, strips it from the note body, and passes correct workRoleId to /time/entries API (Dwain Henderson Jr)
  2026-04-13 v2.8.0 - Ticket search feature: 'tickets for [company]', 'open tickets for [company]', 'all tickets for [company]' — returns embed list with #ID, subject, status, and direct CW link per ticket; fuzzy company matching with numbered picker; supports open-only and all-tickets filters (Dwain Henderson Jr)
"""

import re
import json
import base64
import lzma
import asyncio
import requests
from pathlib import Path
try:
    import anthropic as _anthropic
except ImportError:
    _anthropic = None
from datetime import datetime, timedelta, time, time
from typing import Optional, Tuple, Dict, Any
try:
    from dateutil.parser import parse as parse_date
    from dateutil.relativedelta import relativedelta
except ImportError:
    parse_date = None
    relativedelta = None
import discord
from discord.ext import commands, tasks


class DiscordTicketBotV2Enhanced(commands.Cog):
    """Enhanced ticket bot with one-shot parsing and scheduling"""
    
    def __init__(self, bot: commands.Bot, config: Dict[str, Any]):
        self.bot = bot
        self.config = config
        self.channel_id = int(config.get("discord_channel_id", 0))
        # Dedicated assistant channels — Miles responds to every message (no @mention needed)
        self.assistant_channel_ids: set = set(int(x) for x in config.get("assistant_channel_ids", []))
        self.guild_id = config.get("discord_guild_id")
        
        # CW API config
        self.cw_base_url = config.get("cw_base_url", "https://na.myconnectwise.net/v4_6_release/apis/3.0")
        self.cw_company = config.get("cw_company")
        self.cw_public_key = config.get("cw_public_key")
        self.cw_private_key = config.get("cw_private_key")
        self.cw_client_id = config.get("cw_client_id")
        self.cw_member_id = config.get("cw_member_id")
        
        # Company mapping: seeded from config, then overwritten by live CW sync on startup
        self.company_mapping = config.get("company_mapping", {})
        self._company_sync_last_run: Optional[datetime] = None
        self.priority_ids = config.get("priority_ids", {})
        self.default_priority_id = config.get("default_priority_id", 8)
        
        # Conversation state (ConnectWise ticket flows)
        self.conversations = {}

        # Assistant mode: per-user short-term message history (DMs / @mentions)
        # { user_id: [ {"role": "user"|"assistant", "content": str}, ... ] }
        self.assistant_conversations: Dict[int, list] = {}
        self._assistant_max_history = 20  # keep last 20 turns per user

        # Persistent memory file — lives in the OpenClaw memory directory
        self._memory_path = Path("/root/.openclaw/SNDayton/memory/miles_assistant_memory.json")
        self._memory_cache: Optional[Dict[str, Any]] = None  # loaded lazily

        # Claude AI client (for Miles:/AI: commands and assistant mode)
        self._claude_key = config.get("anthropic_api_key", "")
        self._claude = None
        if _anthropic and self._claude_key:
            try:
                self._claude = _anthropic.Anthropic(api_key=self._claude_key)
            except Exception as e:
                print(f"[Miles] Claude init failed: {e}")
    
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

        # Guard: subject must be DIFFERENT from the client name (or a fragment of it).
        # If the only text is the client name, subject extraction will return the client
        # name itself — that is NOT a real subject, so treat it as missing.
        if result["subject"] and result["client_name"]:
            subj_clean = result["subject"].strip().lower()
            client_clean = result["client_name"].strip().lower()
            # Reject subject if it IS the client name, starts with it, or is contained in it
            if (subj_clean == client_clean
                    or subj_clean in client_clean
                    or client_clean in subj_clean
                    or client_clean.split()[0] in subj_clean.split()):
                result["subject"] = None

        # A ticket is only "complete" (skip conversational flow) when it has BOTH
        # a client name AND a real subject that is distinct from the client name.
        result["complete"] = bool(result["client_name"] and result["subject"])

        return result
    
    def _extract_client_name(self, text: str) -> Optional[str]:
        """Extract client name from text"""
        # Look for exact matches first
        for company_name in self.company_mapping.keys():
            if re.search(rf'\b{re.escape(company_name)}\b', text, re.IGNORECASE):
                return company_name
        
        # Fuzzy match if no exact match — require at least 2 meaningful words to match,
        # or the single word must be at least 5 chars (avoids 'LLC', 'Inc', etc. triggering a match)
        STOPWORDS = {'llc', 'inc', 'corp', 'co', 'the', 'and', 'of', 'for', 'ltd'}
        words = [w.lower() for w in text.split()]
        best_match = None
        best_score = 0
        for company_name in self.company_mapping.keys():
            company_words = [w.lower() for w in company_name.split() if w.lower() not in STOPWORDS]
            if not company_words:
                continue
            matched = [w for w in company_words if w in words and len(w) >= 4]
            score = len(matched)
            if score > best_score and (score >= 2 or (score == 1 and len(matched[0]) >= 6)):
                best_score = score
                best_match = company_name
        return best_match
    
    @staticmethod
    def _edit_distance(a: str, b: str) -> int:
        """Levenshtein edit distance between two strings."""
        if len(a) < len(b):
            a, b = b, a
        if not b:
            return len(a)
        prev = list(range(len(b) + 1))
        for i, ca in enumerate(a):
            curr = [i + 1]
            for j, cb in enumerate(b):
                curr.append(min(prev[j + 1] + 1, curr[j] + 1, prev[j] + (ca != cb)))
            prev = curr
        return prev[-1]

    def _fuzzy_suggest_clients(self, query: str, top_n: int = 3) -> list:
        """
        Score every company in the mapping against the query string and return
        the top_n closest matches as a list of company name strings.
        Uses substring overlap AND edit-distance so near-typos like 'buddy' vs 'budde' score.
        """
        STOPWORDS = {'llc', 'inc', 'corp', 'co', 'the', 'and', 'of', 'for', 'ltd', 'services', 'solutions'}
        query_lower = query.lower()
        query_words = [w for w in re.split(r'\W+', query_lower) if w and w not in STOPWORDS and len(w) >= 3]

        scores = []
        for company_name in self.company_mapping.keys():
            name_lower = company_name.lower()
            name_words = [w for w in re.split(r'\W+', name_lower) if w and w not in STOPWORDS and len(w) >= 3]
            score = 0

            for qw in query_words:
                for nw in name_words:
                    # Exact substring containment
                    if qw in nw or nw in qw:
                        score += len(min(qw, nw, key=len)) * 2
                    else:
                        # Edit-distance similarity: reward close matches
                        max_len = max(len(qw), len(nw))
                        dist = self._edit_distance(qw, nw)
                        # Allow 1 edit per 4 chars (e.g. 'buddy'/'budde' = 1 edit in 5 chars → scores)
                        if dist <= max(1, max_len // 4):
                            score += (max_len - dist) * 1  # softer weight than exact match

            # Bonus: whole query string is a substring of company name or vice versa
            if query_lower in name_lower or name_lower in query_lower:
                score += 10

            if score > 0:
                scores.append((score, company_name))

        scores.sort(key=lambda x: -x[0])
        return [name for _, name in scores[:top_n]]

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
        """Download a Discord attachment (image, PDF, or any file) and upload it to ConnectWise
        as a ticket document. Works for images, PDFs, and all other file types."""
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
            content_type = img_resp.headers.get('Content-Type', 'application/octet-stream')
            if not filename:
                filename = _os.path.basename(image_url.split('?')[0]) or 'attachment'
            # Infer content type from extension if server didn't return a useful one
            ext = _os.path.splitext(filename)[1].lower()
            ext_map = {
                '.pdf': 'application/pdf',
                '.png': 'image/png',
                '.jpg': 'image/jpeg',
                '.jpeg': 'image/jpeg',
                '.gif': 'image/gif',
                '.webp': 'image/webp',
                '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                '.txt': 'text/plain',
                '.zip': 'application/zip',
            }
            if ext in ext_map:
                content_type = ext_map[ext]
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
            print(f"  [file] Uploaded {filename} -> CW document #{doc_id} on ticket #{ticket_id}")
            return {"status": "success", "doc_id": doc_id, "filename": filename}
        except Exception as e:
            print(f"  [file] Upload failed for {image_url}: {e}")
            return {"status": "error", "error": str(e)}

    def _search_tickets(self, company_id: int, open_only: bool = True) -> list:
        """Fetch tickets from ConnectWise for a given company ID.
        Returns list of dicts with id, summary, status name.
        """
        auth = base64.b64encode(
            f"{self.cw_company}+{self.cw_public_key}:{self.cw_private_key}".encode()
        ).decode()
        headers = {
            "Authorization": f"Basic {auth}",
            "clientId": self.cw_client_id,
            "Accept": "application/json",
            "Content-Type": "application/json"
        }
        conditions = f"company/id={company_id}"
        if open_only:
            conditions += " AND closedFlag=false"
        try:
            resp = requests.get(
                f"{self.cw_base_url}/service/tickets",
                headers=headers,
                params={
                    "conditions": conditions,
                    "fields": "id,summary,status",
                    "pageSize": 50,
                    "orderBy": "id desc"
                },
                timeout=15
            )
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            print(f"[search_tickets] Error: {e}")
            return []

    async def _send_ticket_search_results(
        self,
        message: discord.Message,
        company_name: str,
        company_id: int,
        open_only: bool = True
    ):
        """Fetch tickets for company_id and reply with a formatted embed list."""
        filter_label = "Open" if open_only else "All"
        # Show a thinking indicator
        async with message.channel.typing():
            tickets = await asyncio.get_event_loop().run_in_executor(
                None, lambda: self._search_tickets(company_id, open_only)
            )
        if not tickets:
            no_msg = (
                f"\U0001f4ed No **{filter_label.lower()} tickets** found for **{company_name}**."
                if open_only
                else f"\U0001f4ed No tickets found for **{company_name}**."
            )
            await message.reply(no_msg, mention_author=False)
            return
        # Build embed
        embed = discord.Embed(
            title=f"\U0001f3ab {filter_label} Tickets \u2014 {company_name}",
            description=f"Showing **{len(tickets)}** {filter_label.lower()} ticket(s)",
            color=discord.Color.blue()
        )
        lines = []
        for t in tickets:
            tid = t.get("id")
            summary = t.get("summary", "(no subject)")[:80]
            status_name = ""
            if isinstance(t.get("status"), dict):
                status_name = t["status"].get("name", "")
            link = self._generate_deep_link(tid)
            lines.append(f"[#{tid} \u2014 {summary}]({link})" + (f" `{status_name}`" if status_name else ""))
        # Discord embed field values are capped at 1024 chars; chunk if needed
        chunk = []
        chunk_size = 0
        field_num = 1
        for line in lines:
            if chunk_size + len(line) + 1 > 1000:
                embed.add_field(name=f"Tickets (cont.)", value="\n".join(chunk), inline=False)
                chunk = []
                chunk_size = 0
                field_num += 1
            chunk.append(line)
            chunk_size += len(line) + 1
        if chunk:
            embed.add_field(name="Tickets", value="\n".join(chunk), inline=False)
        embed.set_footer(text=f"ConnectWise \u2022 {filter_label} tickets for {company_name}")
        await message.reply(embed=embed, mention_author=False)

    def log_time(self, ticket_id: int, hours: float, notes: str = "", work_role_id: int = None) -> dict:
        """Create a time entry on a ConnectWise ticket via /time/entries"""
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
            "chargeToId": ticket_id,
            "chargeToType": "ServiceTicket",
            "member": {"identifier": self.cw_member_id},
            "actualHours": round(hours, 2),
            "billableOption": "Billable",
            "notes": notes or ""
        }
        if work_role_id:
            payload["workRole"] = {"id": work_role_id}
        try:
            resp = requests.post(
                f"{self.cw_base_url}/time/entries",
                headers=headers,
                json=payload,
                timeout=10
            )
            resp.raise_for_status()
            data = resp.json()
            return {"status": "success", "time_id": data.get("id"), "hours": hours}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def _parse_time_range(self, text: str):
        """Extract hours from a time range like '22:00 - 22:45' or '10:00-11:30'.
        Returns (hours_float, cleaned_text) or (None, original_text)."""
        pattern = re.compile(r'\b(\d{1,2}):(\d{2})\s*[-\u2013]\s*(\d{1,2}):(\d{2})\b')
        m = pattern.search(text)
        if not m:
            return None, text
        sh, sm, eh, em = int(m.group(1)), int(m.group(2)), int(m.group(3)), int(m.group(4))
        start_min = sh * 60 + sm
        end_min = eh * 60 + em
        if end_min <= start_min:
            end_min += 24 * 60  # crossed midnight
        hours = round((end_min - start_min) / 60, 2)
        cleaned = pattern.sub('', text).strip().lstrip('- ').strip()
        return hours, cleaned

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

        # ── Ticket search intent ──────────────────────────────────────────────
        # Matches: "what tickets are open for X", "show all tickets for X",
        #          "list tickets for X", "tickets for X", "open tickets X"
        search_match = re.search(
            r'(?i)(?:what|show|list|get|find|search|display)?\s*'
            r'(?:(?:all|open|closed|active)\s+)?'
            r'tickets?\s+(?:for|from|of|on|by|with)?\s+(.+)',
            text
        )
        if search_match:
            # Also detect if user wants all tickets vs open only
            open_only = not re.search(r'\ball\b', text, re.IGNORECASE)
            # If 'closed' is mentioned, show all (closed+open)
            if re.search(r'\bclosed\b', text, re.IGNORECASE):
                open_only = False
            raw_name = search_match.group(1).strip()
            # Strip trailing punctuation
            raw_name = re.sub(r'[?!.]+$', '', raw_name).strip()
            # Look up the company in our mapping
            company_name = self._extract_client_name(raw_name)
            if not company_name:
                # Try fuzzy suggestions
                suggestions = self._fuzzy_suggest_clients(raw_name)
                if suggestions:
                    lines = [f"❓ I don't recognize **\"{raw_name}\"**. Did you mean one of these?\n"]
                    for i, name in enumerate(suggestions, 1):
                        lines.append(f"`{i}` {name}")
                    lines.append(f"`{len(suggestions)+1}` None of these")
                    lines.append("\n*(Reply with a number)*")
                    # Store context so user can pick
                    self.conversations[message.author.id] = {
                        'mode': 'ticket_search_clarify',
                        'stage': 'pick',
                        'data': {
                            'suggestions': suggestions,
                            'none_idx': len(suggestions) + 1,
                            'open_only': open_only
                        }
                    }
                    await message.reply("\n".join(lines), mention_author=False)
                    return
                else:
                    await message.reply(
                        f"❌ I couldn't find **\"{raw_name}\"** in ConnectWise.\n"
                        f"👉 [Add them here: New Company in ConnectWise](https://na.myconnectwise.net/v2025_1/ConnectWise.aspx?routeTo=NewCompany)",
                        mention_author=False
                    )
                    return
            # Company found — look up its CW ID
            company_id = self.company_mapping.get(company_name)
            if not company_id:
                await message.reply(f"❌ Found client **{company_name}** in local list but couldn't get their ConnectWise ID. Try `Miles: refresh clients`.")
                return
            await self._send_ticket_search_results(message, company_name, company_id, open_only)
            return

        # ── 'add time entry HH:MM - HH:MM' without a ticket number ────────────
        # e.g. "add time entry 22:00 - 22:45" with no ticket number supplied
        if re.match(r'(?i)^\s*add\s+time\s+entry\b', text):
            ticket_in_msg = re.search(r'#(\d{4,6})\b|\bticket\s+#?(\d{4,6})\b', text)
            if not ticket_in_msg:
                # No ticket number — ask for it and store context
                self.conversations[message.author.id] = {
                    'mode': 'time_entry_ticket_prompt',
                    'stage': 'ticket_id',
                    'data': {'pending_text': text}
                }
                await message.reply(
                    "\U0001f3ab Which ticket should I add this time entry to? (e.g., `#31661`)"
                )
                return
            # Ticket number found — fall through to normal update_match routing

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
        # Final fallback: bare standalone 4-6 digit number anywhere in the message
        if not update_match:
            update_match = re.search(r'(?<![\w.])([3-9]\d{4})(?![\w.])', text)
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
            # Strip lead-in phrases to isolate just the company name the user typed
            clean = re.sub(
                r'(?i)^\s*(?:make|create|open|log|submit|add|new)?\s*(?:a\s+|an\s+)?'
                r'(?:new\s+)?(?:ticket|issue|case|request)\s+(?:for|to|with)?\s*',
                '', message.content
            ).strip()
            # Also strip trailing description after a period or comma
            clean = re.split(r'[.,]\s+(?:they|the|it|this|he|she|please|description)', clean, flags=re.IGNORECASE)[0].strip()
            # Grab the first capitalised name-like phrase from the cleaned text
            raw_name = re.match(r'([A-Z][\w\s&\'.-]{1,40}?)(?:\s*[.,]|\s+(?:they|the|it|has|have|is|are|problem|issue|camera|computer|server)|$)', clean)
            typed_name = raw_name.group(1).strip() if raw_name else clean[:40].strip()
            await self._send_client_clarify_prompt(message, typed_name, text)
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

    def _extract_work_role(self, note: str):
        """Extract 'Work Role: <name>' line from note text.
        Returns (work_role_id_or_None, cleaned_note_without_work_role_line).
        Uses fuzzy matching against the CW work role map."""
        # Static map of CW work role names -> IDs (from /time/workRoles)
        WORK_ROLE_MAP = {
            "software deployment & configuration": 4,
            "it consulting & advisory services": 5,
            "sales": 8,
            "office work": 9,
            "consultant": 12,
            "contractor": 13,
            "(30mins)": 14,
            "(1hr)": 15,
            "(2hr)": 16,
            "(project) 5-10hr": 17,
            "hardware repair & maintenance": 18,
            "administrative work": 19,
            "hardware installation & configuration": 20,
            "end-user training & onboarding": 21,
        }
        # Match 'Work Role: <value>' line (case-insensitive, handles em-dash variants)
        pattern = re.compile(r'(?im)^\s*work\s+role\s*:\s*(.+?)\s*$')
        m = pattern.search(note)
        if not m:
            return None, note
        raw_role = m.group(1).strip()
        # Strip taxable/non-taxable suffix for matching
        role_clean = re.sub(r'\s*[\u2014\-]+\s*(taxable|non.taxable).*$', '', raw_role, flags=re.IGNORECASE).strip().lower()
        # Exact match first
        role_id = WORK_ROLE_MAP.get(role_clean)
        if not role_id:
            # Fuzzy: find the work role name with the most word overlap
            best_id, best_score = None, 0
            query_words = set(role_clean.split())
            for name, rid in WORK_ROLE_MAP.items():
                name_words = set(name.split())
                score = len(query_words & name_words)
                if score > best_score:
                    best_score, best_id = score, rid
            if best_score > 0:
                role_id = best_id
        # Remove the Work Role line from the note
        cleaned = pattern.sub('', note).strip()
        return role_id, cleaned

    async def _handle_ticket_update(self, message: discord.Message, ticket_id: int, note: str, hours: float = None):
        """Add a note to an existing ConnectWise ticket and optionally log time"""

        # Strip 'add time entry' prefix if present (e.g. 'add time entry 22:00 - 22:45')
        note = re.sub(r'(?i)^\s*add\s+time\s+entry\s*', '', note or '').strip()

        # Extract 'Work Role: <name>' line and resolve to CW work role ID
        work_role_id, note = self._extract_work_role(note)

        # Try to extract a time range from the note text (e.g. '22:00 - 22:45')
        if hours is None:
            detected_hours, note = self._parse_time_range(note)
            if detected_hours is not None:
                hours = detected_hours

        # If note is empty after stripping, prompt for one (unless we have hours — then it's OK)
        if not note and hours is None:
            await message.reply(f"\U0001f4dd What update should I add to ticket #{ticket_id}?")
            self.conversations[message.author.id] = {
                "mode": "update",
                "stage": "note",
                "data": {"ticket_id": ticket_id}
            }
            return

        # If note is empty but we have hours, use a default note
        if not note and hours is not None:
            note = f"Time entry logged: {hours} hrs"

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

        # Post the note
        update_result = self.update_ticket(ticket_id, note)
        if update_result["status"] != "success":
            await message.reply(f"❌ Failed to update ticket: {update_result.get('error')}")
            return

        # Upload any Discord attachments (images, PDFs, files) to ConnectWise
        uploaded = []
        if message.attachments:
            for att in message.attachments:
                result = self.upload_image_to_ticket(ticket_id, att.url, att.filename)
                if result["status"] == "success":
                    uploaded.append(att.filename)

        # If no time provided yet, ask for it and save state
        if hours is None:
            self.conversations[message.author.id] = {
                "mode": "update",
                "stage": "time",
                "data": {
                    "ticket_id": ticket_id,
                    "note": note,
                    "uploaded": uploaded,
                    "company_name": company_name,
                    "summary": summary,
                    "work_role_id": work_role_id
                }
            }
            await message.reply("⏱️ Time to log? (or 'skip')", mention_author=False)
            return

        # Log time entry if hours were provided
        time_logged = None
        work_role_name = None
        if hours:
            time_result = self.log_time(ticket_id, hours, note, work_role_id=work_role_id)
            if time_result["status"] == "success":
                time_logged = hours
                # Resolve work role name for display
                if work_role_id:
                    WORK_ROLE_NAMES = {
                        4: "Software Deployment & Configuration", 5: "IT Consulting & Advisory Services",
                        8: "Sales", 9: "Office Work", 12: "Consultant", 13: "Contractor",
                        14: "(30MINS)", 15: "(1HR)", 16: "(2HR)", 17: "(Project) 5-10hr",
                        18: "Hardware Repair & Maintenance", 19: "Administrative Work",
                        20: "Hardware Installation & Configuration", 21: "End-User Training & Onboarding"
                    }
                    work_role_name = WORK_ROLE_NAMES.get(work_role_id)
                print(f"  ⏱️ Time entry logged: {hours}h on ticket #{ticket_id}" + (f" [{work_role_name}]" if work_role_name else ""))
            else:
                print(f"  ⚠️ Time entry failed: {time_result.get('error')}")

        # Build confirmation embed
        embed = discord.Embed(
            title=f"✅ Ticket #{ticket_id} Updated",
            description=summary,
            color=discord.Color.blue(),
            url=self._generate_deep_link(ticket_id)
        )
        embed.add_field(name="Client", value=company_name, inline=True)
        if time_logged:
            time_display = f"{time_logged} hrs"
            if work_role_name:
                time_display += f" ({work_role_name})"
            embed.add_field(name="Time Logged", value=time_display, inline=True)
        embed.add_field(name="Note Added", value=note[:500], inline=False)
        if uploaded:
            embed.add_field(name="Files Uploaded", value="\n".join(uploaded), inline=False)
        embed.add_field(name="Link", value=f"[Open in ConnectWise]({self._generate_deep_link(ticket_id)})", inline=False)
        embed.set_footer(text=f"Updated by {message.author.name}")
        await message.reply(embed=embed, mention_author=False)
        print(f"✅ Updated ticket #{ticket_id} with note{', ' + str(time_logged) + 'h time entry' if time_logged else ''}{' + ' + str(len(uploaded)) + ' file(s)' if uploaded else ''}")
    
    async def _create_ticket_and_schedule(self, message: discord.Message, parsed: Dict[str, Any]):
        """Create ticket and optionally schedule appointment"""
        company_id = self.company_mapping.get(parsed["client_name"])
        if not company_id:
            await self._send_client_clarify_prompt(message, parsed["client_name"], None, parsed=parsed)
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
    
    async def _send_client_clarify_prompt(
        self,
        message: discord.Message,
        typed_name: str,
        original_text: Optional[str],
        parsed: Optional[Dict[str, Any]] = None
    ):
        """
        Present a numbered clarification prompt when the client name can't be confirmed.
        Shows top 3 fuzzy matches + 'None of these' with a link to add in ConnectWise.
        Stores conversation state so the user's numbered reply resumes ticket creation.
        """
        suggestions = self._fuzzy_suggest_clients(typed_name, top_n=3)
        cw_url = self.config.get('cw_base_url', 'https://na.myconnectwise.net/v4_6_release/apis/3.0')
        cw_root = cw_url.split('/v4_6')[0] if '/v4_6' in cw_url else 'https://na.myconnectwise.net'
        add_company_url = (
            f"{cw_root}/v4_6_release/services/system_io/router/openrecord.rails"
            f"?locale=en_US&recordType=CompanyFV&recid=0&newWindow=false"
        )

        lines = [f"\u2753 I don't recognize **\"{typed_name}\"**. Did you mean one of these?\n"]
        for i, name in enumerate(suggestions, start=1):
            lines.append(f"`{i}` {name}")
        none_idx = len(suggestions) + 1
        lines.append(
            f"`{none_idx}` None of these — the client needs to exist in ConnectWise first.\n"
            f"\U0001f449 [Add them here: New Company in ConnectWise]({add_company_url})"
        )
        lines.append("\n*(Reply with a number, or type the correct client name)*")

        await message.reply("\n".join(lines), mention_author=False)

        # Save state so we can resume when the user replies
        self.conversations[message.author.id] = {
            "mode": "client_clarify",
            "stage": "pick",
            "data": {
                "typed_name": typed_name,
                "suggestions": suggestions,
                "none_idx": none_idx,
                "original_text": original_text,
                "parsed": parsed,          # may be None if we came from the no-match path
                "add_company_url": add_company_url,
            }
        }

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
    
    # ============================================================================
    # LIVE COMPANY SYNC
    # ============================================================================

    def _fetch_cw_companies(self) -> Dict[str, int]:
        """
        Pull the full active company list from ConnectWise Manage.
        Returns a dict of {company_name: company_id} for all active companies.
        Fetches in pages of 1000 until all records are retrieved.
        """
        auth = base64.b64encode(
            f"{self.cw_company}+{self.cw_public_key}:{self.cw_private_key}".encode()
        ).decode()
        headers = {
            "Authorization": f"Basic {auth}",
            "clientId": self.cw_client_id,
            "Accept": "application/json"
        }
        mapping = {}
        page = 1
        page_size = 1000
        while True:
            try:
                resp = requests.get(
                    f"{self.cw_base_url}/company/companies",
                    headers=headers,
                    params={
                        "conditions": "status/name='Active'",
                        "fields": "id,name",
                        "pageSize": page_size,
                        "page": page
                    },
                    timeout=15
                )
                resp.raise_for_status()
                data = resp.json()
                if not data:
                    break
                for company in data:
                    name = company.get("name", "").strip()
                    cid = company.get("id")
                    if name and cid:
                        mapping[name] = cid
                if len(data) < page_size:
                    break
                page += 1
            except Exception as e:
                print(f"[CompanySync] Page {page} fetch error: {e}")
                break
        return mapping

    async def _sync_companies(self, notify_channel_id: Optional[int] = None, notify_message=None) -> int:
        """
        Refresh self.company_mapping from ConnectWise.
        Returns the number of companies loaded.
        Optionally posts a Discord reply to notify_message, or posts to notify_channel_id.
        """
        print("[CompanySync] Fetching company list from ConnectWise...")
        try:
            mapping = await asyncio.get_event_loop().run_in_executor(
                None, self._fetch_cw_companies
            )
            if mapping:
                self.company_mapping = mapping
                self._company_sync_last_run = datetime.utcnow()
                count = len(mapping)
                print(f"[CompanySync] ✅ Loaded {count} companies from ConnectWise")
                if notify_message:
                    await notify_message.reply(
                        f"✅ Client list refreshed from ConnectWise — **{count} companies** loaded.",
                        mention_author=False
                    )
                return count
            else:
                print("[CompanySync] ⚠️ No companies returned — keeping existing list")
                if notify_message:
                    await notify_message.reply(
                        "⚠️ ConnectWise returned no companies. Keeping existing client list.",
                        mention_author=False
                    )
                return 0
        except Exception as e:
            print(f"[CompanySync] ❌ Sync failed: {e}")
            if notify_message:
                await notify_message.reply(
                    f"❌ Client list refresh failed: {e}",
                    mention_author=False
                )
            return 0

    @tasks.loop(hours=24)
    async def _company_refresh_task(self):
        """Background task: refresh company list from ConnectWise every 24 hours"""
        await self._sync_companies()

    @_company_refresh_task.before_loop
    async def _before_company_refresh(self):
        """Wait until the bot is ready before starting the background refresh loop"""
        await self.bot.wait_until_ready()

    # ============================================================================
    # PERSISTENT MEMORY — read/write the miles_assistant_memory.json file
    # ============================================================================

    def _load_memory(self) -> Dict[str, Any]:
        """Load the persistent memory file, returning a dict. Creates it if missing."""
        if self._memory_cache is not None:
            return self._memory_cache
        if self._memory_path.exists():
            try:
                self._memory_cache = json.loads(self._memory_path.read_text(encoding="utf-8"))
                return self._memory_cache
            except Exception as e:
                print(f"[Memory] Load error: {e}")
        # Default empty structure
        self._memory_cache = {
            "version": 1,
            "updatedAt": None,
            "owner": "Dwain Henderson Jr — Superior Networks LLC, Dayton OH",
            "facts": [],
            "summary": ""
        }
        return self._memory_cache

    def _save_memory(self, data: Dict[str, Any]) -> None:
        """Persist the memory dict to disk."""
        try:
            data["updatedAt"] = datetime.utcnow().isoformat() + "Z"
            self._memory_path.parent.mkdir(parents=True, exist_ok=True)
            self._memory_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
            self._memory_cache = data
        except Exception as e:
            print(f"[Memory] Save error: {e}")

    def _memory_context_block(self) -> str:
        """Return a compact string representation of persistent memory for the system prompt."""
        mem = self._load_memory()
        parts = []
        if mem.get("summary"):
            parts.append(f"PERSISTENT MEMORY SUMMARY:\n{mem['summary']}")
        if mem.get("facts"):
            facts_text = "\n".join(f"- {f}" for f in mem["facts"][-40:])  # last 40 facts
            parts.append(f"KNOWN FACTS:\n{facts_text}")
        return "\n\n".join(parts) if parts else "No persistent memory yet."

    async def _maybe_update_memory(self, user_message: str, assistant_reply: str) -> None:
        """Ask Claude to extract any new facts from the exchange and update memory."""
        if not self._claude:
            return
        mem = self._load_memory()
        existing_facts = "\n".join(f"- {f}" for f in mem.get("facts", []))
        extraction_prompt = (
            f"You are a memory manager for an AI assistant named Miles.\n"
            f"Review this conversation exchange and extract any NEW facts worth remembering "
            f"about the user, their business, clients, schedule, preferences, or ongoing projects.\n"
            f"Only extract facts that are not already in the existing facts list.\n"
            f"Return ONLY a JSON object with two keys:\n"
            f"  \"new_facts\": list of new fact strings (empty list if none)\n"
            f"  \"updated_summary\": a concise 3-5 sentence summary of everything known about the user\n\n"
            f"EXISTING FACTS:\n{existing_facts or 'None yet'}\n\n"
            f"USER SAID: {user_message[:500]}\n"
            f"MILES REPLIED: {assistant_reply[:500]}"
        )
        try:
            resp = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self._claude.messages.create(
                    model="claude-haiku-4-5",
                    max_tokens=600,
                    messages=[{"role": "user", "content": extraction_prompt}]
                )
            )
            raw = resp.content[0].text.strip()
            # Strip markdown code fences if present
            raw = re.sub(r'^```(?:json)?\s*', '', raw, flags=re.MULTILINE)
            raw = re.sub(r'```\s*$', '', raw, flags=re.MULTILINE).strip()
            extracted = json.loads(raw)
            new_facts = extracted.get("new_facts", [])
            updated_summary = extracted.get("updated_summary", "")
            if new_facts or updated_summary:
                mem["facts"] = mem.get("facts", []) + new_facts
                if updated_summary:
                    mem["summary"] = updated_summary
                self._save_memory(mem)
                if new_facts:
                    print(f"[Memory] Stored {len(new_facts)} new fact(s)")
        except Exception as e:
            print(f"[Memory] Update skipped: {e}")

    # ============================================================================
    # ASSISTANT MODE — full conversational AI with memory (DMs / @mentions)
    # ============================================================================

    async def _handle_assistant_message(self, message: discord.Message, content: str) -> None:
        """
        Handle a message in assistant mode (DMs or @mentions outside #cw-ticketing).
        Uses Claude Haiku with persistent memory and per-user short-term history.
        """
        if not self._claude:
            await message.reply(
                "⚠️ I'm not configured for general assistant mode yet — "
                "the AI key is missing. I can still handle ConnectWise tasks in #cw-ticketing.",
                mention_author=False
            )
            return

        user_id = message.author.id
        user_name = message.author.display_name

        # Strip @Miles mention from content if present
        clean_content = re.sub(r'<@!?\d+>', '', content).strip()

        # ── Build user message content (text + any image attachments) ───────
        # Claude vision format: content is a list of blocks when images are present
        user_content_blocks = []

        # Process image attachments for vision
        image_extensions = {'.png', '.jpg', '.jpeg', '.gif', '.webp'}
        media_type_map = {
            '.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg',
            '.gif': 'image/gif', '.webp': 'image/webp'
        }
        for att in message.attachments:
            ext = '.' + att.filename.rsplit('.', 1)[-1].lower() if '.' in att.filename else ''
            if ext in image_extensions:
                try:
                    import urllib.request as _ur
                    img_bytes = await asyncio.get_event_loop().run_in_executor(
                        None, lambda url=att.url: _ur.urlopen(url, timeout=15).read()
                    )
                    img_b64 = base64.b64encode(img_bytes).decode('utf-8')
                    user_content_blocks.append({
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": media_type_map.get(ext, 'image/jpeg'),
                            "data": img_b64
                        }
                    })
                except Exception as img_err:
                    print(f"[Vision] Failed to load image {att.filename}: {img_err}")

        # Add text block (required even if empty when images are present)
        if clean_content:
            user_content_blocks.append({"type": "text", "text": clean_content})
        elif user_content_blocks:
            # Images only, no text — add a prompt
            user_content_blocks.append({"type": "text", "text": "Please describe and analyze this image."})
        else:
            # No text, no images
            await message.reply("Hey! What can I help you with?", mention_author=False)
            return

        # Use plain string for text-only messages (keeps history serializable)
        user_message_content = user_content_blocks if user_content_blocks else clean_content

        # Build short-term history for this user
        history = self.assistant_conversations.get(user_id, [])
        history.append({"role": "user", "content": user_message_content})

        # Build system prompt with persistent memory injected
        memory_block = self._memory_context_block()
        system_prompt = (
            f"You are Miles, a smart personal assistant for {user_name} at Superior Networks LLC "
            f"(a one-person MSP in Dayton, Ohio run by Dwain Henderson Jr).\n"
            f"You are helpful, concise, and professional. You remember context across conversations.\n"
            f"For ConnectWise ticket work, direct the user to the #cw-ticketing channel.\n\n"
            f"{memory_block}"
        )

        try:
            async with message.channel.typing():
                resp = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: self._claude.messages.create(
                        model="claude-haiku-4-5",
                        max_tokens=1000,
                        system=system_prompt,
                        messages=history[-self._assistant_max_history:]
                    )
                )
            reply_text = resp.content[0].text.strip()
        except Exception as e:
            await message.reply(f"❌ Assistant error: {e}", mention_author=False)
            return

        # Update short-term history
        history.append({"role": "assistant", "content": reply_text})
        # Trim to max history
        if len(history) > self._assistant_max_history * 2:
            history = history[-(self._assistant_max_history * 2):]
        self.assistant_conversations[user_id] = history

        await message.reply(reply_text, mention_author=False)

        # Fire-and-forget memory update (don't block the reply)
        asyncio.create_task(self._maybe_update_memory(clean_content, reply_text))

    @commands.Cog.listener()
    async def on_ready(self):
        """Bot ready — pull company list from ConnectWise on startup, then start 24h refresh loop"""
        print(f"✅ Enhanced Bot v2 logged in as {self.bot.user}")
        count = await self._sync_companies()
        if count:
            print(f"[CompanySync] Startup sync complete: {count} companies ready")
        if not self._company_refresh_task.is_running():
            self._company_refresh_task.start()
            print("[CompanySync] 24-hour background refresh task started")
    
    # ============================================================================
    # MILES: / AI: COMMAND SYSTEM
    # ============================================================================

    async def _handle_miles_command(self, message: discord.Message, instruction: str, body: str) -> bool:
        """
        Handle a Miles:/AI: prefixed instruction.
        Returns True if handled, False if not recognized (caller should fall through).

        Supported instructions:
          summarize ticket <N>          - fetch ticket and post a summary
          translate to <lang>           - AI translate the body text
          add a priority note at the top - prepend PRIORITY header to body
          list in bullet style          - format body as bullets
          numbered list                 - format body as numbered list
          send to AI / ask AI           - send body to Claude and reply with response
          help / commands               - list available commands
        """
        instr = instruction.strip().lower()
        print(f"[Miles] Command: '{instr}' | Body: '{body[:60]}'")

        # ── help / commands ──────────────────────────────────────────────────
        if re.search(r'^(help|commands|what can you do)$', instr):
            last_sync = (
                self._company_sync_last_run.strftime("%Y-%m-%d %H:%M UTC")
                if self._company_sync_last_run else "not yet synced"
            )
            help_text = (
                "**Miles Command Reference** (use `Miles:` or `AI:` prefix)\n"
                "```\n"
                "Miles: summarize ticket 31666\n"
                "Miles: translate to Spanish\n"
                "Miles: add a priority note at the top\n"
                "Miles: list in bullet style\n"
                "Miles: numbered list\n"
                "Miles: send to AI <question or text>\n"
                "Miles: refresh clients\n"
                "Miles: client count\n"
                "Miles: help\n"
                "```\n"
                "You can also combine with ticket updates:\n"
                "`add to ticket 31666 - <note>\nMiles: list in bullet style`\n"
                f"\n\U0001f504 Client list last synced: **{last_sync}** (auto-refreshes every 24 hours)"
            )
            await message.reply(help_text, mention_author=False)
            return True

        # ── refresh clients ──────────────────────────────────────────────────
        if re.search(r'refresh\s+clients?|reload\s+clients?|sync\s+clients?|update\s+clients?', instr):
            await message.reply(
                "🔄 Refreshing client list from ConnectWise... (this may take a few seconds)",
                mention_author=False
            )
            await self._sync_companies(notify_message=message)
            return True

        # ── client count ─────────────────────────────────────────────────────
        if re.search(r'client\s+count|how\s+many\s+clients?|list\s+clients?', instr):
            count = len(self.company_mapping)
            last_sync = (
                self._company_sync_last_run.strftime("%Y-%m-%d %H:%M UTC")
                if self._company_sync_last_run else "not yet synced"
            )
            await message.reply(
                f"🏢 **{count} active clients** loaded from ConnectWise.\n"
                f"🕒 Last synced: {last_sync}\n"
                f"🔄 Auto-refreshes every 24 hours. Use `Miles: refresh clients` to force a refresh.",
                mention_author=False
            )
            return True

        # ── summarize ticket N ───────────────────────────────────────────────
        m = re.search(r'summarize\s+ticket\s+#?(\d{4,6})', instr)
        if m:
            ticket_id = int(m.group(1))
            result = self.get_ticket(ticket_id)
            if result["status"] != "success":
                await message.reply(f"❌ Ticket #{ticket_id} not found")
                return True
            t = result["ticket"]
            company = t.get("company", {}).get("name", "Unknown")
            summary = t.get("summary", "(no summary)")
            status = t.get("status", {}).get("name", "Unknown")
            priority = t.get("priority", {}).get("name", "Unknown")
            # Ask Claude for a plain-English summary if available
            ai_summary = ""
            if self._claude:
                try:
                    resp = self._claude.messages.create(
                        model="claude-haiku-4-5",
                        max_tokens=300,
                        messages=[{"role": "user", "content": f"Summarize this IT ticket in 2-3 sentences for a technician:\nClient: {company}\nSummary: {summary}\nStatus: {status}\nPriority: {priority}"}]
                    )
                    ai_summary = resp.content[0].text.strip()
                except Exception as e:
                    print(f"[Miles] Claude error: {e}")
            embed = discord.Embed(
                title=f"📋 Ticket #{ticket_id} Summary",
                description=ai_summary or summary,
                color=discord.Color.blurple(),
                url=self._generate_deep_link(ticket_id)
            )
            embed.add_field(name="Client", value=company, inline=True)
            embed.add_field(name="Status", value=status, inline=True)
            embed.add_field(name="Priority", value=priority, inline=True)
            embed.add_field(name="Subject", value=summary[:200], inline=False)
            await message.reply(embed=embed, mention_author=False)
            return True

        # ── translate to <lang> ──────────────────────────────────────────────
        m = re.search(r'translate\s+(?:to\s+)?([a-z]+)', instr)
        if m:
            lang = m.group(1).capitalize()
            text_to_translate = body or "(no text provided)"
            if not self._claude:
                await message.reply("❌ AI not available — Claude API key not configured")
                return True
            try:
                resp = self._claude.messages.create(
                    model="claude-haiku-4-5",
                    max_tokens=500,
                    messages=[{"role": "user", "content": f"Translate the following text to {lang}. Return only the translated text, nothing else:\n\n{text_to_translate}"}]
                )
                translated = resp.content[0].text.strip()
                await message.reply(f"🌐 **{lang} translation:**\n{translated}", mention_author=False)
            except Exception as e:
                await message.reply(f"❌ Translation failed: {e}")
            return True

        # ── add a priority note at the top ───────────────────────────────────
        if re.search(r'add\s+(?:a\s+)?priority\s+note', instr):
            if not body:
                await message.reply("❌ No text provided to add a priority note to")
                return True
            priority_note = f"⚠️ PRIORITY\n{'─'*30}\n{body}"
            await message.reply(f"📌 Priority note formatted:\n```\n{priority_note}\n```", mention_author=False)
            return True

        # ── list in bullet style ─────────────────────────────────────────────
        if re.search(r'list\s+(?:it\s+)?in\s+bullet(?:\s+style|s)?', instr):
            if not body:
                await message.reply("❌ No text provided to format as bullets")
                return True
            lines = [ln.strip() for ln in body.splitlines() if ln.strip()]
            bulleted = '\n'.join(f'• {ln}' for ln in lines)
            await message.reply(f"📝 Formatted:\n{bulleted}", mention_author=False)
            return True

        # ── numbered list ────────────────────────────────────────────────────
        if re.search(r'numbered\s+list|number\s+(?:the\s+)?(?:items|lines)', instr):
            if not body:
                await message.reply("❌ No text provided to number")
                return True
            lines = [ln.strip() for ln in body.splitlines() if ln.strip()]
            numbered = '\n'.join(f'{i+1}. {ln}' for i, ln in enumerate(lines))
            await message.reply(f"📝 Numbered:\n{numbered}", mention_author=False)
            return True

        # ── send to AI / ask AI ──────────────────────────────────────────────
        if re.search(r'^(send\s+to\s+ai|ask\s+ai|ai\s+response|ask\s+claude)', instr) or (not body and instr):
            prompt = body or instruction
            if not self._claude:
                await message.reply("❌ AI not available — Claude API key not configured")
                return True
            try:
                async with message.channel.typing():
                    resp = self._claude.messages.create(
                        model="claude-haiku-4-5",
                        max_tokens=800,
                        system="You are Miles, an IT support assistant for Superior Networks LLC. Be concise and professional.",
                        messages=[{"role": "user", "content": prompt}]
                    )
                    ai_reply = resp.content[0].text.strip()
                await message.reply(f"🤖 **Miles (AI):**\n{ai_reply}", mention_author=False)
            except Exception as e:
                await message.reply(f"❌ AI request failed: {e}")
            return True

        # ── unrecognized instruction — send to Claude as a general question ──
        full_prompt = f"{instruction}\n\n{body}".strip() if body else instruction
        if self._claude:
            try:
                async with message.channel.typing():
                    resp = self._claude.messages.create(
                        model="claude-haiku-4-5",
                        max_tokens=800,
                        system="You are Miles, an IT support assistant for Superior Networks LLC. Be concise and professional.",
                        messages=[{"role": "user", "content": full_prompt}]
                    )
                    ai_reply = resp.content[0].text.strip()
                await message.reply(f"🤖 **Miles (AI):**\n{ai_reply}", mention_author=False)
                return True
            except Exception as e:
                print(f"[Miles] Fallback AI error: {e}")
        return False

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """
        Main message listener — dual-mode routing:
          - #cw-ticketing channel: ConnectWise only (tickets, time entries, updates)
          - DMs, any channel where @Miles is mentioned, and dedicated assistant channels: full assistant with persistent memory
        """
        if message.author == self.bot.user:
            return

        is_dm = isinstance(message.channel, discord.DMChannel)
        is_cw_channel = message.channel.id == self.channel_id
        is_mentioned = self.bot.user in message.mentions
        is_assistant_channel = message.channel.id in self.assistant_channel_ids

        # Ignore messages that don't involve Miles at all
        if not (is_dm or is_cw_channel or is_mentioned or is_assistant_channel):
            return

        print(f"\n[{datetime.now().isoformat()}] {message.author}: {message.content[:80]}")

        user_id = message.author.id
        content = message.content.strip()

        # ── ASSISTANT MODE: DMs, @mentions, and dedicated assistant channels ──
        if (is_dm or is_mentioned or is_assistant_channel) and not is_cw_channel:
            # Miles: / AI: commands still work in assistant mode
            miles_match = re.search(r'(?im)^(?:miles|ai)\s*:\s*(.+?)(?:\n|$)', content)
            if miles_match:
                instruction = miles_match.group(1).strip()
                body = content[:miles_match.start()].strip()
                handled = await self._handle_miles_command(message, instruction, body)
                if handled:
                    return
            # Route everything else to the conversational assistant
            await self._handle_assistant_message(message, content)
            return

        # ── CW-TICKETING MODE: ConnectWise only ──────────────────────────────
        # ── Miles:/AI: command prefix detection ──────────────────────────────
        # Matches: 'Miles: <instruction>' or 'AI: <instruction>'
        # Can appear anywhere in the message (inline with a note or standalone)
        miles_match = re.search(
            r'(?im)^(?:miles|ai)\s*:\s*(.+?)(?:\n|$)',
            content
        )
        if miles_match:
            instruction = miles_match.group(1).strip()
            # Body = everything before the Miles:/AI: line
            body = content[:miles_match.start()].strip()
            handled = await self._handle_miles_command(message, instruction, body)
            if handled:
                return
            # If not handled, fall through to normal routing with body only
            content = body if body else content
        
        # Try enhanced parsing first (one-shot)
        if user_id not in self.conversations:
            await self.handle_ticket_request(message, content)
        else:
            conv = self.conversations[user_id]

            # ── Cancel at any point ──────────────────────────────────────────
            if content.strip().lower() in ("cancel", "stop", "abort", "quit", "nevermind", "never mind"):
                del self.conversations[user_id]
                await message.reply("\u274c Operation cancelled.", mention_author=False)
                return

            # ── 'add time entry' — waiting for ticket number ─────────────────
            if conv.get("mode") == "time_entry_ticket_prompt" and conv.get("stage") == "ticket_id":
                pending_text = conv["data"]["pending_text"]
                del self.conversations[user_id]
                # Extract ticket number from the reply
                t_match = re.search(r'#?(\d{4,6})\b', content)
                if not t_match:
                    await message.reply("\u274c Couldn't find a ticket number. Please include the ticket number (e.g., `#31661`)")
                    return
                ticket_id = int(t_match.group(1))
                # Route to update handler with the original time-entry text as the note
                await self._handle_ticket_update(message, ticket_id, pending_text)
                return

            # ── ticket_search_clarify — user is picking a company for ticket search ──
            if conv.get("mode") == "ticket_search_clarify" and conv.get("stage") == "pick":
                data = conv["data"]
                suggestions = data["suggestions"]
                none_idx = data["none_idx"]
                open_only = data.get("open_only", True)
                reply = content.strip()
                chosen_name = None
                chosen_id = None
                num_match = re.fullmatch(r'(\d+)', reply)
                if num_match:
                    choice = int(num_match.group(1))
                    if 1 <= choice <= len(suggestions):
                        chosen_name = suggestions[choice - 1]
                        chosen_id = self.company_mapping.get(chosen_name)
                    elif choice == none_idx:
                        del self.conversations[user_id]
                        await message.reply(
                            "Got it. I couldn't find the company. Please check the name or add them to ConnectWise.",
                            mention_author=False
                        )
                        return
                else:
                    # User typed a name — try to match
                    chosen_name = self._extract_client_name(reply)
                    if chosen_name:
                        chosen_id = self.company_mapping.get(chosen_name)
                if not chosen_name or not chosen_id:
                    await message.reply(
                        f"\u274c I didn't understand that choice. Please reply with a number (1\u2013{none_idx}).",
                        mention_author=False
                    )
                    return
                del self.conversations[user_id]
                await self._send_ticket_search_results(message, chosen_name, chosen_id, open_only)
                return

            # ── client_clarify — user is picking from a numbered suggestion list ──
            if conv.get("mode") == "client_clarify" and conv.get("stage") == "pick":
                data = conv["data"]
                suggestions = data["suggestions"]
                none_idx = data["none_idx"]
                reply = content.strip()

                # Determine which company the user chose
                chosen_name = None
                num_match = re.fullmatch(r'(\d+)', reply)
                if num_match:
                    choice = int(num_match.group(1))
                    if 1 <= choice <= len(suggestions):
                        chosen_name = suggestions[choice - 1]
                    elif choice == none_idx:
                        # User confirmed the client doesn't exist
                        del self.conversations[user_id]
                        await message.reply(
                            f"Got it. Add **{data['typed_name']}** to ConnectWise first, then type "
                            f"`Miles: refresh clients` and re-send your message.\n"
                            f"\U0001f449 [New Company in ConnectWise]({data['add_company_url']})",
                            mention_author=False
                        )
                        return
                else:
                    # User typed a name directly — try to match it
                    chosen_name = self._extract_client_name(reply)
                    if not chosen_name:
                        # Still no match — re-prompt with new suggestions
                        del self.conversations[user_id]
                        await self._send_client_clarify_prompt(message, reply, data.get("original_text"), parsed=data.get("parsed"))
                        return

                if not chosen_name:
                    await message.reply(
                        f"\u274c I didn't understand that choice. Please reply with a number (1–{none_idx}).",
                        mention_author=False
                    )
                    return

                # We have a confirmed company name — resume ticket creation
                del self.conversations[user_id]
                original_text = data.get("original_text")
                existing_parsed = data.get("parsed")

                if existing_parsed:
                    # We already have a parsed ticket dict — just swap in the confirmed name
                    existing_parsed["client_name"] = chosen_name
                    existing_parsed["complete"] = True
                    await self._create_ticket_and_schedule(message, existing_parsed)
                elif original_text:
                    # Re-parse the original message with the confirmed name substituted
                    fixed_text = re.sub(
                        re.escape(data["typed_name"]), chosen_name, original_text, flags=re.IGNORECASE, count=1
                    )
                    if chosen_name not in fixed_text:
                        fixed_text = chosen_name + " " + original_text
                    await self.handle_ticket_request(message, fixed_text)
                else:
                    # Fallback: start conversational flow with the confirmed name
                    await self._start_conversational_flow(message, {
                        "client_name": chosen_name,
                        "subject": None,
                        "description": None,
                        "hours": None,
                        "schedule_date": None,
                        "schedule_time": None,
                        "priority": None,
                        "complete": False
                    })
                return

            # Handle update note stage
            if conv.get("mode") == "update" and conv.get("stage") == "note":
                ticket_id = conv["data"]["ticket_id"]
                del self.conversations[user_id]
                await self._handle_ticket_update(message, ticket_id, content)
            elif conv.get("mode") == "update" and conv.get("stage") == "time":
                data = conv["data"]
                del self.conversations[user_id]
                hours = None
                if content.strip().lower() not in ("skip", "s", "no", "none"):
                    # Try time range first (e.g. 22:00 - 22:45)
                    hours, _ = self._parse_time_range(content)
                    if hours is None:
                        h_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:h(?:ours?|rs?)?)', content, re.IGNORECASE)
                        m_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:m(?:in(?:utes?)?)?)', content, re.IGNORECASE)
                        if h_match:
                            hours = float(h_match.group(1))
                        elif m_match:
                            hours = round(float(m_match.group(1)) / 60, 2)
                        else:
                            try:
                                hours = float(content.strip())
                            except ValueError:
                                pass
                # Log time if provided
                time_logged = None
                work_role_name = None
                if hours:
                    saved_work_role_id = data.get("work_role_id")
                    time_result = self.log_time(data["ticket_id"], hours, data["note"], work_role_id=saved_work_role_id)
                    if time_result["status"] == "success":
                        time_logged = hours
                        if saved_work_role_id:
                            WORK_ROLE_NAMES = {
                                4: "Software Deployment & Configuration", 5: "IT Consulting & Advisory Services",
                                8: "Sales", 9: "Office Work", 12: "Consultant", 13: "Contractor",
                                14: "(30MINS)", 15: "(1HR)", 16: "(2HR)", 17: "(Project) 5-10hr",
                                18: "Hardware Repair & Maintenance", 19: "Administrative Work",
                                20: "Hardware Installation & Configuration", 21: "End-User Training & Onboarding"
                            }
                            work_role_name = WORK_ROLE_NAMES.get(saved_work_role_id)
                        print(f"  ⏱️ Time entry logged: {hours}h on ticket #{data['ticket_id']}" + (f" [{work_role_name}]" if work_role_name else ""))
                    else:
                        print(f"  ⚠️ Time entry failed: {time_result.get('error')}")
                embed = discord.Embed(
                    title=f"✅ Ticket #{data['ticket_id']} Updated",
                    description=data.get("summary", ""),
                    color=discord.Color.blue(),
                    url=self._generate_deep_link(data["ticket_id"])
                )
                embed.add_field(name="Client", value=data.get("company_name", ""), inline=True)
                if time_logged:
                    time_display = f"{time_logged} hrs"
                    if work_role_name:
                        time_display += f" ({work_role_name})"
                    embed.add_field(name="Time Logged", value=time_display, inline=True)
                embed.add_field(name="Note Added", value=data["note"][:500], inline=False)
                if data.get("uploaded"):
                    embed.add_field(name="Files Uploaded", value="\n".join(data["uploaded"]), inline=False)
                embed.add_field(name="Link", value=f"[Open in ConnectWise]({self._generate_deep_link(data['ticket_id'])})", inline=False)
                embed.set_footer(text=f"Updated by {message.author.name}")
                await message.reply(embed=embed, mention_author=False)
            else:
                # Handle conversational create flow
                stage = conv.get("stage")
                data = conv["data"]

                # ── Cancel at any point ──────────────────────────────────────
                if content.strip().lower() in ("cancel", "stop", "abort", "quit", "nevermind", "never mind"):
                    del self.conversations[user_id]
                    await message.reply("❌ Ticket creation cancelled.", mention_author=False)
                    return

                if stage == "subject":
                    data["subject"] = content.strip()
                    conv["stage"] = "description"
                    await message.reply("📝 Description/Details?", mention_author=False)

                elif stage == "description":
                    data["description"] = content.strip() if content.strip().lower() != "skip" else ""
                    conv["stage"] = "time"
                    await message.reply("⏱️ Time to log? (or 'skip')", mention_author=False)

                elif stage == "time":
                    hours = None
                    if content.strip().lower() != "skip":
                        hours_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:h(?:ours?|rs?)?)', content, re.IGNORECASE)
                        mins_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:m(?:in(?:utes?)?)?)', content, re.IGNORECASE)
                        if hours_match:
                            hours = float(hours_match.group(1))
                        elif mins_match:
                            hours = round(float(mins_match.group(1)) / 60, 2)
                        else:
                            try:
                                hours = float(content.strip())
                            except ValueError:
                                pass
                    data["hours"] = hours
                    del self.conversations[user_id]
                    # Build a parsed dict and create the ticket
                    parsed = {
                        "client_name": data["company_name"],
                        "subject": data["subject"],
                        "description": data.get("description", ""),
                        "hours": hours,
                        "schedule_date": data.get("schedule_date"),
                        "schedule_time": data.get("schedule_time"),
                        "priority": data.get("priority"),
                        "note_body": None,
                        "complete": True
                    }
                    await self._create_ticket_and_schedule(message, parsed)

def setup(bot: commands.Bot, config: Dict[str, Any]):
    """Load cog into bot"""
    bot.add_cog(DiscordTicketBotV2Enhanced(bot, config))
