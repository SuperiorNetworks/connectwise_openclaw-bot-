#!/usr/bin/env python3
"""
Name: discord_ticket_listener_v2.py
Version: 2.0.0
Purpose: Conversational Discord bot for ConnectWise ticket creation/updates
Author: Dwain Henderson Jr. | Superior Networks LLC
Contact: Your MSP Administrator
Copyright: 2026, Superior Networks LLC
Location: /root/.openclaw/SNDayton/scripts/discord_ticket_listener_v2.py

What This Script Does:
  - Connects to Discord using bot token
  - Monitors cw-ticketing channel for conversational ticket requests
  - Supports flexible, natural language ticket creation and updates
  - Asks clarifying questions in sequence
  - Auto-creates tickets/notes + time entries in ConnectWise
  - Maintains per-user conversation state

Input:
  - Discord channel messages
  - Config: discord_cw_ticket_config.json

Output:
  - Confirmation embeds posted to Discord
  - Console logs of all activity

Dependencies:
  - discord.py
  - requests
  - json
  - base64
  - lzma

Change Log:
  2026-04-08 v2.0.0 - Conversational flow with flexible input (Dwain Henderson Jr)
"""

import os
import sys
import json
import base64
import lzma
import re
from datetime import datetime, timedelta

import discord
from discord.ext import commands
import requests
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

class DiscordTicketBotV2(commands.Cog):
    CW_BASE64_ALPHA = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789$_"
    
    def __init__(self, bot, config):
        self.bot = bot
        self.config = config
        self.cw_auth = self._setup_cw_auth()
        self.company_map = config.get("company_mapping", {})
        self.priority_ids = config.get("priority_ids", {})
        self.default_priority = config.get("default_priority_id", 8)
        self.channel_id = int(config.get("discord_channel_id"))
        
        # Per-user conversation state: user_id -> {"mode": "create|update", "data": {...}, "stage": "..."}
        self.conversations = {}
    
    def _cw_base64_encode(self, data: bytes) -> str:
        """Encode using ConnectWise's custom Base64 alphabet"""
        encoded = base64.b64encode(data).decode('ascii')
        encoded = encoded.replace('+', '$').replace('/', '_')
        return encoded.rstrip('=')
    
    def _generate_cw_link(self, ticket_id: int) -> str:
        """Generate ConnectWise deep link for a ticket"""
        import time
        import random
        
        state = {
            "ticketId": ticket_id,
            "memberId": "YourMemberId",
            "timestamp": int(time.time() * 1000),
            "random": random.randint(0, 2147483647)
        }
        
        json_str = json.dumps(state, separators=(',', ':'))
        json_bytes = json_str.encode('utf-8')
        compressed = lzma.compress(json_bytes, format=lzma.FORMAT_ALONE, preset=1)
        encoded = self._cw_base64_encode(compressed)
        
        return f"https://na.myconnectwise.net/v2025_1/ConnectWise.aspx?locale=en_US#{encoded}??ServiceTicket"
    
    def _setup_cw_auth(self):
        """Setup ConnectWise authentication headers"""
        company = self.config.get("cw_company", "YOUR_COMPANY")
        public_key = self.config.get("cw_public_key", "YOUR_PUBLIC_KEY")
        private_key = self.config.get("cw_private_key", "YOUR_PRIVATE_KEY")
        client_id = self.config.get("cw_client_id", "YOUR_CLIENT_ID")
        
        auth_str = base64.b64encode(f"{company}+{public_key}:{private_key}".encode()).decode()
        
        return {
            "Authorization": f"Basic {auth_str}",
            "clientId": client_id,
            "Accept": "application/json",
            "Content-Type": "application/json"
        }
    
    def _find_company_id(self, text: str) -> tuple:
        """Extract company ID from text"""
        text_lower = text.lower()
        
        for company_name, company_id in self.company_map.items():
            if company_name.lower() in text_lower:
                return company_id, company_name
        
        return None, None
    
    def _find_ticket_number(self, text: str) -> Optional[int]:
        """Extract ticket number from text"""
        match = re.search(r'#(\d+)', text)
        if match:
            return int(match.group(1))
        return None
    
    def _extract_hours(self, text: str) -> Optional[float]:
        """Extract hours from text"""
        match = re.search(r'(\d+(?:\.\d+)?)\s*(hr|hour|hrs|hours|min|minute|minutes)', text.lower())
        if match:
            value = float(match.group(1))
            unit = match.group(2)
            if unit.startswith('min'):
                return value / 60
            return value
        return None
    
    def _extract_priority(self, text: str) -> tuple:
        """Extract priority from text"""
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
        """Create a schedule entry (time entry) for billable hours"""
        url = f"{self.config['cw_base_url']}/schedule/entries"
        
        now = datetime.utcnow()
        end_time = now + timedelta(hours=hours)
        
        payload = {
            "objectId": ticket_id,
            "type": {"id": 4},
            "member": {"id": 147},
            "dateStart": now.isoformat() + "Z",
            "dateEnd": end_time.isoformat() + "Z",
            "status": {"id": 2}
        }
        
        try:
            resp = requests.post(url, headers=self.cw_auth, json=payload, timeout=10)
            resp.raise_for_status()
            return {"status": "success", "entry_id": resp.json().get("id")}
        except requests.exceptions.RequestException as e:
            return {"status": "error", "error": f"Schedule entry failed: {str(e)}"}
    
    def _create_cw_ticket(self, company_id: int, company_name: str, summary: str, description: str, priority_id: int, priority_name: str) -> Dict[str, Any]:
        """Create ticket in ConnectWise"""
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
    
    def _add_note_to_ticket(self, ticket_id: int, note_text: str, hours: Optional[float] = None) -> Dict[str, Any]:
        """Add note to ticket and create time entry if hours provided"""
        url = f"{self.config['cw_base_url']}/service/tickets/{ticket_id}/notes"
        
        payload = {
            "text": note_text,
            "detailDescriptionFlag": True
        }
        
        try:
            resp = requests.post(url, headers=self.cw_auth, json=payload, timeout=10)
            resp.raise_for_status()
            
            note_data = resp.json()
            
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
    
    async def _ask_question(self, message, question: str) -> str:
        """Ask user a question and wait for response"""
        await message.channel.send(f"**{question}**")
    
    async def _process_create_flow(self, message, user_id: int, conv_state: Dict) -> None:
        """Process ticket creation flow"""
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
            await self._ask_question(message, f"📋 Subject for {company_name}?")
        
        elif stage == "subject":
            data["summary"] = content
            conv_state["stage"] = "description"
            await self._ask_question(message, "📝 Description/Details?")
        
        elif stage == "description":
            data["description"] = content
            priority_id, priority_name = self._extract_priority(content)
            data["priority_id"] = priority_id
            data["priority_name"] = priority_name
            conv_state["stage"] = "time"
            await self._ask_question(message, "⏱️ Time to log? (or 'skip')")
        
        elif stage == "time":
            if content.lower() == "skip":
                hours = None
            else:
                hours = self._extract_hours(content)
                if hours is None:
                    await message.reply("❌ Could not parse hours. Try 'skip' or a number (e.g., '5 hours')")
                    return
            
            # Create ticket
            result = self._create_cw_ticket(
                data["company_id"],
                data["company_name"],
                data["summary"],
                data["description"],
                data["priority_id"],
                data["priority_name"]
            )
            
            if result.get("status") == "success":
                ticket_id = result["ticket_id"]
                
                # Add time entry if hours provided
                if hours and hours > 0:
                    self._create_schedule_entry(ticket_id, hours)
                    time_text = f" + {hours}h time entry"
                else:
                    time_text = ""
                
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
                print(f"✅ Created ticket #{ticket_id} for {data['company_name']}{time_text}")
                
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
    
    async def _process_update_flow(self, message, user_id: int, conv_state: Dict) -> None:
        """Process ticket update flow"""
        stage = conv_state.get("stage", "note")
        data = conv_state.get("data", {})
        
        content = message.content.strip()
        
        if stage == "note":
            data["note"] = content
            conv_state["stage"] = "time"
            await self._ask_question(message, "⏱️ Time to log? (or 'skip')")
        
        elif stage == "time":
            if content.lower() == "skip":
                hours = None
            else:
                hours = self._extract_hours(content)
                if hours is None:
                    await message.reply("❌ Could not parse hours. Try 'skip' or a number (e.g., '5 hours')")
                    return
            
            # Add note and time entry
            result = self._add_note_to_ticket(data["ticket_id"], data["note"], hours)
            
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
        """Listen for messages in cw-ticketing channel"""
        if message.author == self.bot.user:
            return
        
        if message.channel.id != self.channel_id:
            return
        
        user_id = message.author.id
        content = message.content.strip()
        
        print(f"\n[{datetime.now().isoformat()}] {message.author}: {content[:80]}")
        
        # Check if user has active conversation
        if user_id in self.conversations:
            conv_state = self.conversations[user_id]
            
            # Check for conversation switch (new ticket or update request)
            if re.search(r'\bnew\b.*\bticket\b', content, re.IGNORECASE):
                # Switch to new ticket
                company_id, company_name = self._find_company_id(content)
                if company_id:
                    self.conversations[user_id] = {
                        "mode": "create",
                        "stage": "subject",
                        "data": {"company_id": company_id, "company_name": company_name}
                    }
                    await self._ask_question(message, f"📋 Subject for {company_name}?")
                    return
            
            ticket_num = self._find_ticket_number(content)
            if ticket_num:
                # Switch to update mode
                self.conversations[user_id] = {
                    "mode": "update",
                    "stage": "note",
                    "data": {"ticket_id": ticket_num}
                }
                await self._ask_question(message, "📝 Note to add?")
                return
            
            # Continue current conversation
            if conv_state.get("mode") == "create":
                await self._process_create_flow(message, user_id, conv_state)
            elif conv_state.get("mode") == "update":
                await self._process_update_flow(message, user_id, conv_state)
        
        else:
            # Start new conversation
            # Detect mode from content
            ticket_num = self._find_ticket_number(content)
            
            if ticket_num:
                # Update mode
                self.conversations[user_id] = {
                    "mode": "update",
                    "stage": "note",
                    "data": {"ticket_id": ticket_num}
                }
                await self._ask_question(message, "📝 Note to add?")
            else:
                # Create mode
                company_id, company_name = self._find_company_id(content)
                if company_id:
                    self.conversations[user_id] = {
                        "mode": "create",
                        "stage": "subject",
                        "data": {"company_id": company_id, "company_name": company_name}
                    }
                    await self._ask_question(message, f"📋 Subject for {company_name}?")
                else:
                    await message.reply("❌ Start with a client name (e.g., 'Positive Electric') or ticket number (e.g., '#31641')")

async def setup_bot(token, config):
    """Initialize and run Discord bot"""
    intents = discord.Intents.default()
    intents.message_content = True
    
    bot = commands.Bot(command_prefix="!", intents=intents)
    await bot.add_cog(DiscordTicketBotV2(bot, config))
    
    async with bot:
        await bot.start(token)

def load_config(config_path=None):
    """Load configuration"""
    if not config_path:
        config_path = Path(__file__).parent.parent / "config" / "discord_cw_ticket_config.json"
    
    with open(config_path) as f:
        return json.load(f)

def main():
    """Main entry point"""
    config = load_config()
    token = os.getenv("DISCORD_BOT_TOKEN")
    if not token:
        raise ValueError("DISCORD_BOT_TOKEN environment variable not set")
    
    print("🤖 Discord Ticket Listener V2 Starting...")
    print(f"📍 Channel: {config['discord_channel_name']} (ID: {config['discord_channel_id']})")
    print(f"🔌 Monitoring {len(config['company_mapping'])} active clients")
    
    import asyncio
    asyncio.run(setup_bot(token, config))

if __name__ == "__main__":
    main()
