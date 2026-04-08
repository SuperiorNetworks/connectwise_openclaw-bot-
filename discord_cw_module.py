"""
Discord Conversational Ticket Bot Module for ConnectWise

This module provides the core bot functionality for creating and updating
ConnectWise tickets via Discord with conversational, flexible input.

Usage:
    from discord_cw_module import DiscordTicketBotV2
    
    bot = DiscordTicketBotV2(config)
    # ... attach to Discord bot as Cog
"""

import discord
from discord.ext import commands
import requests
import json
import base64
import lzma
import re
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Tuple

class DiscordTicketBotV2(commands.Cog):
    """Conversational Discord bot for ConnectWise ticket management"""
    
    CW_BASE64_ALPHA = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789$_"
    
    def __init__(self, bot: commands.Bot, config: Dict[str, Any]):
        """
        Initialize bot with configuration
        
        Args:
            bot: Discord bot instance
            config: Configuration dict with channel IDs, CW credentials, company mapping
        """
        self.bot = bot
        self.config = config
        self.cw_auth = self._setup_cw_auth()
        self.company_map = config.get("company_mapping", {})
        self.priority_ids = config.get("priority_ids", {})
        self.default_priority = config.get("default_priority_id", 8)
        self.channel_id = int(config.get("discord_channel_id"))
        
        # Per-user conversation state
        self.conversations: Dict[int, Dict[str, Any]] = {}
    
    def _cw_base64_encode(self, data: bytes) -> str:
        """Encode bytes using ConnectWise's custom Base64 alphabet"""
        encoded = base64.b64encode(data).decode('ascii')
        encoded = encoded.replace('+', '$').replace('/', '_')
        return encoded.rstrip('=')
    
    def _generate_cw_link(self, ticket_id: int) -> str:
        """
        Generate ConnectWise v2025_1 deep link for a ticket
        
        Args:
            ticket_id: Numeric ticket ID
            
        Returns:
            Full deep link URL
        """
        import time
        import random
        
        state = {
            "ticketId": ticket_id,
            "memberId": "DHenderson",
            "timestamp": int(time.time() * 1000),
            "random": random.randint(0, 2147483647)
        }
        
        json_str = json.dumps(state, separators=(',', ':'))
        json_bytes = json_str.encode('utf-8')
        compressed = lzma.compress(json_bytes, format=lzma.FORMAT_ALONE, preset=1)
        encoded = self._cw_base64_encode(compressed)
        
        return f"https://na.myconnectwise.net/v2025_1/ConnectWise.aspx?locale=en_US#{encoded}??ServiceTicket"
    
    def _setup_cw_auth(self) -> Dict[str, str]:
        """Setup ConnectWise authentication headers from environment or config"""
        company = self.config.get("cw_company", "superiornet")
        public_key = self.config.get("cw_public_key")
        private_key = self.config.get("cw_private_key")
        client_id = self.config.get("cw_client_id")
        
        if not all([public_key, private_key, client_id]):
            raise ValueError("Missing ConnectWise credentials in config")
        
        auth_str = base64.b64encode(
            f"{company}+{public_key}:{private_key}".encode()
        ).decode()
        
        return {
            "Authorization": f"Basic {auth_str}",
            "clientId": client_id,
            "Accept": "application/json",
            "Content-Type": "application/json"
        }
    
    def _find_company_id(self, text: str) -> Tuple[Optional[int], Optional[str]]:
        """
        Extract company ID and name from text using fuzzy matching
        
        Args:
            text: User input text
            
        Returns:
            Tuple of (company_id, company_name) or (None, None)
        """
        text_lower = text.lower()
        
        for company_name, company_id in self.company_map.items():
            if company_name.lower() in text_lower:
                return company_id, company_name
        
        return None, None
    
    def _find_ticket_number(self, text: str) -> Optional[int]:
        """Extract ticket number from text (e.g., #31641)"""
        match = re.search(r'#(\d+)', text)
        return int(match.group(1)) if match else None
    
    def _extract_hours(self, text: str) -> Optional[float]:
        """
        Extract hours from text supporting multiple formats
        
        Examples:
            "5 hours" → 5.0
            "2.5 hrs" → 2.5
            "30 minutes" → 0.5
        """
        match = re.search(
            r'(\d+(?:\.\d+)?)\s*(hr|hour|hrs|hours|min|minute|minutes)',
            text.lower()
        )
        if match:
            value = float(match.group(1))
            unit = match.group(2)
            return value / 60 if unit.startswith('min') else value
        return None
    
    def _extract_priority(self, text: str) -> Tuple[int, str]:
        """Extract priority from text (critical/high/medium/low or p1-p4)"""
        text_lower = text.lower()
        
        if re.search(r'\bcritical\b|p1\b|p\s*1\b', text_lower):
            return self.priority_ids.get("critical", 6), "Critical"
        elif re.search(r'\bhigh\b|p2\b|p\s*2\b', text_lower):
            return self.priority_ids.get("high", 15), "High"
        elif re.search(r'\bmedium\b|p3\b|p\s*3\b', text_lower):
            return self.priority_ids.get("medium", 8), "Medium"
        elif re.search(r'\blow\b|p4\b|p\s*4\b', text_lower):
            return self.priority_ids.get("low", 7), "Low"
        
        return self.default_priority, "Medium"
    
    def _create_schedule_entry(self, ticket_id: int, hours: float) -> Dict[str, Any]:
        """Create a time entry in ConnectWise schedule"""
        url = f"{self.config['cw_base_url']}/schedule/entries"
        
        now = datetime.utcnow()
        end_time = now + timedelta(hours=hours)
        
        payload = {
            "objectId": ticket_id,
            "type": {"id": 4},  # Service ticket
            "member": {"id": self.config.get("cw_member_id")},
            "dateStart": now.isoformat() + "Z",
            "dateEnd": end_time.isoformat() + "Z",
            "status": {"id": 2}  # Firm
        }
        
        try:
            resp = requests.post(url, headers=self.cw_auth, json=payload, timeout=10)
            resp.raise_for_status()
            return {"status": "success", "entry_id": resp.json().get("id")}
        except requests.exceptions.RequestException as e:
            return {"status": "error", "error": f"Schedule entry failed: {str(e)}"}
    
    def create_ticket(
        self,
        company_id: int,
        company_name: str,
        summary: str,
        description: str,
        priority_id: int,
        priority_name: str
    ) -> Dict[str, Any]:
        """
        Create a ConnectWise ticket
        
        Returns:
            Dict with status, ticket_id, and CW deep link
        """
        url = f"{self.config['cw_base_url']}/service/tickets"
        
        payload = {
            "company": {"id": company_id},
            "summary": summary,
            "initialDescription": description,
            "priority": {"id": priority_id}
        }
        
        try:
            resp = requests.post(url, headers=self.cw_auth, json=payload, timeout=10)
            resp.raise_for_status()
            
            ticket_data = resp.json()
            ticket_id = ticket_data.get("id")
            
            return {
                "status": "success",
                "ticket_id": ticket_id,
                "company_name": company_name,
                "summary": summary,
                "priority_name": priority_name,
                "cw_link": self._generate_cw_link(ticket_id)
            }
        except requests.exceptions.RequestException as e:
            return {
                "status": "error",
                "error": f"ConnectWise API failed: {str(e)}",
                "company_name": company_name,
                "summary": summary
            }
    
    def add_note_to_ticket(
        self,
        ticket_id: int,
        note_text: str,
        hours: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Add note to ticket and optionally create time entry
        
        Returns:
            Dict with status, note text, and time entry status
        """
        url = f"{self.config['cw_base_url']}/service/tickets/{ticket_id}/notes"
        
        payload = {
            "text": note_text,
            "detailDescriptionFlag": True
        }
        
        try:
            resp = requests.post(url, headers=self.cw_auth, json=payload, timeout=10)
            resp.raise_for_status()
            
            result = {
                "status": "success",
                "ticket_id": ticket_id,
                "note": note_text,
                "cw_link": self._generate_cw_link(ticket_id)
            }
            
            if hours and hours > 0:
                schedule_result = self._create_schedule_entry(ticket_id, hours)
                result["hours"] = hours
                result["schedule_status"] = schedule_result.get("status")
                if schedule_result.get("status") == "error":
                    result["schedule_error"] = schedule_result.get("error")
            
            return result
        except requests.exceptions.RequestException as e:
            return {
                "status": "error",
                "ticket_id": ticket_id,
                "error": f"Failed to add note: {str(e)}"
            }
    
    async def ask_question(self, message, question: str) -> None:
        """Post a question to the Discord channel"""
        await message.channel.send(f"**{question}**")
    
    async def process_create_flow(
        self,
        message,
        user_id: int,
        conv_state: Dict
    ) -> None:
        """Process ticket creation conversational flow"""
        stage = conv_state.get("stage", "company")
        data = conv_state.get("data", {})
        
        content = message.content.strip()
        
        if stage == "company":
            company_id, company_name = self._find_company_id(content)
            if not company_id:
                await message.reply("❌ Client not recognized. Try again (e.g., 'Positive Electric')")
                return
            
            data["company_id"] = company_id
            data["company_name"] = company_name
            conv_state["stage"] = "subject"
            await self.ask_question(message, f"📋 Subject for {company_name}?")
        
        elif stage == "subject":
            data["summary"] = content
            conv_state["stage"] = "description"
            await self.ask_question(message, "📝 Description/Details?")
        
        elif stage == "description":
            data["description"] = content
            priority_id, priority_name = self._extract_priority(content)
            data["priority_id"] = priority_id
            data["priority_name"] = priority_name
            conv_state["stage"] = "time"
            await self.ask_question(message, "⏱️ Time to log? (or 'skip')")
        
        elif stage == "time":
            hours = None if content.lower() == "skip" else self._extract_hours(content)
            
            if hours is None and content.lower() != "skip":
                await message.reply("❌ Could not parse hours. Try 'skip' or a number (e.g., '5 hours')")
                return
            
            # Create ticket
            result = self.create_ticket(
                data["company_id"],
                data["company_name"],
                data["summary"],
                data["description"],
                data["priority_id"],
                data["priority_name"]
            )
            
            if result.get("status") == "success":
                ticket_id = result["ticket_id"]
                
                if hours and hours > 0:
                    self._create_schedule_entry(ticket_id, hours)
                
                embed = discord.Embed(
                    title=f"✅ Ticket #{ticket_id} Created",
                    description=data["summary"],
                    color=discord.Color.green(),
                    url=result["cw_link"]
                )
                embed.add_field(name="Client", value=data["company_name"], inline=True)
                embed.add_field(name="Priority", value=data["priority_name"], inline=True)
                if hours and hours > 0:
                    embed.add_field(name="Time", value=f"{hours} hours", inline=True)
                embed.add_field(name="CW Link", value=f"[Open Ticket]({result['cw_link']})", inline=False)
                
                await message.reply(embed=embed, mention_author=False)
                print(f"✅ Created ticket #{ticket_id} for {data['company_name']}")
                
                del self.conversations[user_id]
            else:
                embed = discord.Embed(
                    title="❌ Failed to Create Ticket",
                    description=result.get("error"),
                    color=discord.Color.red()
                )
                embed.add_field(name="Client", value=data["company_name"], inline=True)
                await message.reply(embed=embed, mention_author=False)
                del self.conversations[user_id]
    
    async def process_update_flow(
        self,
        message,
        user_id: int,
        conv_state: Dict
    ) -> None:
        """Process ticket update conversational flow"""
        stage = conv_state.get("stage", "note")
        data = conv_state.get("data", {})
        
        content = message.content.strip()
        
        if stage == "note":
            data["note"] = content
            conv_state["stage"] = "time"
            await self.ask_question(message, "⏱️ Time to log? (or 'skip')")
        
        elif stage == "time":
            hours = None if content.lower() == "skip" else self._extract_hours(content)
            
            if hours is None and content.lower() != "skip":
                await message.reply("❌ Could not parse hours. Try 'skip' or a number (e.g., '5 hours')")
                return
            
            # Add note and time entry
            result = self.add_note_to_ticket(data["ticket_id"], data["note"], hours)
            
            if result.get("status") == "success":
                embed = discord.Embed(
                    title=f"✅ Note Added to Ticket #{result['ticket_id']}",
                    description=result["note"],
                    color=discord.Color.green(),
                    url=result["cw_link"]
                )
                if hours and hours > 0:
                    time_status = "✅" if result.get("schedule_status") == "success" else "⚠️"
                    embed.add_field(name="Time Entry", value=f"{time_status} {hours} hours", inline=True)
                embed.add_field(name="CW Link", value=f"[Open Ticket]({result['cw_link']})", inline=False)
                
                await message.reply(embed=embed, mention_author=False)
                print(f"✅ Added note to ticket #{result['ticket_id']}")
                
                del self.conversations[user_id]
            else:
                embed = discord.Embed(
                    title="❌ Failed to Add Note",
                    description=result.get("error"),
                    color=discord.Color.red()
                )
                embed.add_field(name="Ticket", value=f"#{data['ticket_id']}", inline=True)
                await message.reply(embed=embed, mention_author=False)
                del self.conversations[user_id]
    
    @commands.Cog.listener()
    async def on_ready(self):
        """Bot ready event"""
        print(f"✅ Bot logged in as {self.bot.user}")
        print(f"📍 Monitoring channel ID: {self.channel_id}")
    
    @commands.Cog.listener()
    async def on_message(self, message):
        """Main message listener for ticket channel"""
        if message.author == self.bot.user or message.channel.id != self.channel_id:
            return
        
        user_id = message.author.id
        content = message.content.strip()
        
        print(f"\n[{datetime.now().isoformat()}] {message.author}: {content[:80]}")
        
        # Check for active conversation
        if user_id in self.conversations:
            conv_state = self.conversations[user_id]
            
            # Check for conversation switch
            if re.search(r'\bnew\b.*\bticket\b', content, re.IGNORECASE):
                company_id, company_name = self._find_company_id(content)
                if company_id:
                    self.conversations[user_id] = {
                        "mode": "create",
                        "stage": "subject",
                        "data": {"company_id": company_id, "company_name": company_name}
                    }
                    await self.ask_question(message, f"📋 Subject for {company_name}?")
                    return
            
            ticket_num = self._find_ticket_number(content)
            if ticket_num:
                self.conversations[user_id] = {
                    "mode": "update",
                    "stage": "note",
                    "data": {"ticket_id": ticket_num}
                }
                await self.ask_question(message, "📝 Note to add?")
                return
            
            # Continue current flow
            if conv_state.get("mode") == "create":
                await self.process_create_flow(message, user_id, conv_state)
            elif conv_state.get("mode") == "update":
                await self.process_update_flow(message, user_id, conv_state)
        
        else:
            # Start new conversation
            ticket_num = self._find_ticket_number(content)
            
            if ticket_num:
                self.conversations[user_id] = {
                    "mode": "update",
                    "stage": "note",
                    "data": {"ticket_id": ticket_num}
                }
                await self.ask_question(message, "📝 Note to add?")
            else:
                company_id, company_name = self._find_company_id(content)
                if company_id:
                    self.conversations[user_id] = {
                        "mode": "create",
                        "stage": "subject",
                        "data": {"company_id": company_id, "company_name": company_name}
                    }
                    await self.ask_question(message, f"📋 Subject for {company_name}?")
                else:
                    await message.reply("❌ Start with a client name (e.g., 'Positive Electric') or ticket number (e.g., '#31641')")
