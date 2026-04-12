# Changelog

All notable changes to the Discord Conversational Ticket Bot will be documented in this file.

## [2.2.0] - 2026-04-12

### Changed
- **No-client-found response (Option A)** — When all lookup passes fail (exact match → fuzzy local → live CW search → still nothing), the bot no longer hard-fails with a red X. It now replies with a clear, instructional message that echoes the unrecognized name, explains the client must exist in ConnectWise first, provides a direct clickable link to the New Company form in ConnectWise, and tells the user to run `Miles: refresh clients` then re-send their message.

## [2.1.0] - 2026-04-12

### Added
- **Live ConnectWise Client Sync** — The bot now pulls the full list of active companies directly from ConnectWise on startup, eliminating the need to hardcode client names in the config file.
- **Background Auto-Refresh** — The client list automatically refreshes every 24 hours in the background without requiring a bot restart.
- **Manual Refresh Commands** — Added `Miles: refresh clients` to force an immediate sync, and `Miles: client count` to check how many clients are loaded and when the last sync occurred.

## [2.0.2] - 2026-04-12

### Fixed
- **`add time entry` without ticket number** — Bot now correctly intercepts messages starting with `add time entry` that have no ticket number. Instead of accidentally creating a new ticket, it asks "Which ticket should I add this time entry to?" and waits for the user to reply with a ticket number (e.g., `#31661`).
- **`add time entry` prefix stripping** — When `add time entry 22:00 - 22:45` is routed to a ticket, the `add time entry` prefix is stripped from the note text before posting to ConnectWise. If the note is empty after stripping (pure time-entry-only message), a default note `Time entry logged: X hrs` is used.
- **Cancel in all conversation modes** — Added cancel detection (`cancel`/`stop`/`abort`/`quit`/`nevermind`) at the top of the conversation handler so it works in all modes including the new `time_entry_ticket_prompt` mode.

## [2.0.1] - 2026-04-11

### Fixed
- **JSON Parse Error** — Fixed a bug where `memory/.dreams/short-term-recall.json` contained non-ASCII characters causing OpenClaw to fail parsing JSON payloads. Deployed a cron-based sanitizer (`openclaw_sanitizer.py`) to continuously clean the file.
- **Bot Authentication** — Corrected the Discord bot token for the Miles bot to ensure proper authentication and connection.
- **Channel ID Type Mismatch** — Fixed an issue where channel IDs were being compared as strings instead of integers, preventing the bot from responding in the correct channel.
- **Ticket ID Reference** — Fixed `Ticket #None` issue by correctly referencing the `id` field instead of `ticketNumber` in the ConnectWise API response.
- **Deep Link URL Format** — Updated the ConnectWise deep link generation to use a stable and reliable format (`fv_sr100_request.rails?service_recid=TICKET_ID`).

### Added
- **Enhanced Natural Language Parsing** — Added over 20 IT action verbs, lead-in phrase stripping, and sentence-based fallback for more robust ticket creation without requiring pipe separators.
- **Summary/Title Label Parsing** — Added support for parsing `Summary:` or `Title:` labels in messages. Text after the label maps directly to the ticket summary, and remaining text goes into the discussion note.
- **Inline Image Uploads** — Implemented inline image uploading via the ConnectWise Documents API (`POST /system/documents` and `POST /service/tickets/{id}/documents`). Images sent via Discord now appear inline in the ConnectWise ticket discussion body, rather than as URL text.
- **Ticket Management Methods** — Added `update_ticket()` and `get_ticket()` methods to the ConnectWise module for improved ticket handling.

## [1.0.0] - 2026-04-08

### Added
- **Conversational ticket creation flow** — Guide users through ticket creation with natural language questions
- **Conversational ticket update flow** — Add notes to existing tickets with optional time tracking
- **Time tracking integration** — Automatically create billable time entries when hours are specified
- **Per-user conversation state** — Maintain separate conversation contexts for each user
- **Mid-stream context switching** — Switch between creating new tickets and updating existing ones mid-conversation
- **Smart priority detection** — Auto-detect priority from keywords (critical/p1, high/p2, medium/p3, low/p4)
- **Flexible time notation parsing** — Support multiple formats (5 hours, 2.5 hrs, 30 minutes, 90 mins)
- **Deep link generation** — Generate v2025_1 ConnectWise deep links with LZMA compression
- **Natural language company matching** — Fuzzy match client names from user input
- **Discord embed responses** — Pretty formatted ticket confirmations with links to ConnectWise
- **Error handling** — Graceful fallbacks with actionable error messages
- **Systemd service** — Optional background service deployment on Linux
- **Comprehensive documentation** — README, SETUP guide, formatting guide, quick start for clients

### Features
- Two-mode conversational interface (create / update)
- ConnectWise API integration (tickets, notes, schedules)
- Per-user conversation persistence
- Automatic schedule entry creation (time tracking)
- v2025_1 deep link generation with LZMA compression
- Priority auto-detection from description text
- Time notation parsing (hours/minutes, flexible formats)
- Company ID mapping (configurable)
- Member ID configuration for time entries

### Documentation
- **README.md** — Feature overview, usage examples, architecture
- **SETUP.md** — Installation, configuration, testing, troubleshooting
- **TICKET_FORMATTING_GUIDE.md** — How to write service tickets following Superior Networks standards
- **QUICK_START_FOR_CLIENTS.md** — Simple guide for MSP clients using the bot
- **CHANGELOG.md** — This file

### Configuration
- **discord_cw_ticket_config.json.template** — Example configuration with all required fields
- Environment variable support for sensitive credentials
- Per-client company mapping
- Configurable priority IDs

### Deployment
- **discord-ticket-bot.service** — Systemd service template for Linux deployment
- Auto-restart on failure
- Journal logging integration

## Future Versions

### [1.1.0] (Planned)
- Work role auto-detection from description text
- Taxable/non-taxable classification in time entries
- Ticket search integration (find recent tickets by client)
- Bulk note updates
- Typing indicators during bot processing
- Reaction-based confirmation (👍 = confirm, ❌ = cancel)

### [1.2.0] (Planned)
- Board auto-assignment based on client/priority
- Custom status workflows per client
- Notification options (@ mention on ticket creation)
- Export to CSV/JSON for reporting
- Analytics dashboard integration

### [2.0.0] (Future)
- Multi-workspace support (manage multiple ConnectWise instances)
- Ticket templates for common issues
- Knowledge base integration
- Client portal integration
- Mobile app support

## Known Limitations

- Single Discord bot instance per channel (no multi-workspace support yet)
- Conversation state lost on bot restart (not persisted to disk)
- No ticket search/lookup (can only update by ticket number if you know it)
- Deep links require v2025_1 ConnectWise (older versions may not work)

## Breaking Changes

None yet (v1.0.0 is initial release)

## Support

For issues, feature requests, or questions:
- Open a GitHub issue
- Contact your MSP administrator

## Contributors

- Superior Networks LLC — Initial implementation & design

## License

© 2026 Superior Networks LLC — MIT License
