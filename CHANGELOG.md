# Changelog

All notable changes to the Discord Conversational Ticket Bot will be documented in this file.

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
