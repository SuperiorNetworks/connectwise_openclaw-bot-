# Changelog

All notable changes to the Discord Conversational Ticket Bot will be documented in this file.

## [2.9.6] - 2026-04-15

### Fixed
- **Time of day now recorded correctly in ConnectWise** — `_parse_time_range` now supports 12-hour am/pm format (`4:30p - 6p`, `4:30pm-6pm`) in addition to 24-hour format. The parsed times are converted from local time (Eastern, UTC-4 by default) to UTC and sent as `timeStart` and `timeEnd` in the time entry payload. Previously, the bot always used the current UTC clock time, causing entries like `4:30 PM EDT` to show as `12:02 AM` in ConnectWise.
- **Inline hours auto-detected** — Plain hour/minute values (`1.5hrs`, `90min`, `2h`) in the initial update message are now extracted automatically. The bot skips the "Time to log?" prompt when hours are already present in the message.
- **`timeEnd` now sent to CW API** — `log_time()` now sends `timeEnd` alongside `timeStart`, so both Start Time and End Time columns populate correctly in ConnectWise.
- **Config key** — Add `"tz_offset_hours": -5` to the bot config for EST (winter), or `-4` for EDT (summer, default).

## [2.9.5] - 2026-04-15

### Fixed
- **Time entry creation was silently failing** — The ConnectWise `/time/entries` API requires a `timeStart` field (ISO 8601 UTC timestamp). The bot was not sending it, causing every time entry POST to return `400 InvalidObject / MissingRequiredField: timeStart`. The current UTC time is now always included in the payload.
- **Wrong member field format** — When `cw_member_id` is a numeric value (e.g., `147`), the CW API expects `{"id": 147}`, not `{"identifier": "147"}`. The bot now auto-detects whether the member ID is numeric or a string username and sends the correct format.
- **`Ticket#NNNNN` (no-space) not recognized** — Commands like `update Ticket#31745 1.5hrs ...` were not being matched by the update regex because it required a space between `ticket` and `#`. The space is now optional in all update/note regex patterns.

## [2.9.4] - 2026-04-14

### Added
- **Universal cancel command** — Typing `stop`, `exit`, `quit`, `cancel`, `abort`, `nevermind`, or `never mind` on a line by itself now immediately cancels any active conversation flow (ticket creation, ticket update, time entry, ticket search company picker). The bot replies with `❌ Operation cancelled.` and clears the pending state.

## [2.9.3] - 2026-04-14

### Added
- **Configurable service board filter** — Ticket search now restricts results to specific ConnectWise service boards. Defaults to `IT Support` and `GTD - Pet_Projects`. Board names are resolved to IDs automatically at bot startup via the CW API. To change the boards, update `ticket_search_boards` in the config JSON (e.g., `["IT Support", "My Other Board"]`). Set to `[]` to disable the filter and return tickets from all boards.

## [2.9.2] - 2026-04-14

### Fixed
- **Embed size limit on large ticket results** — Ticket searches returning 50 tickets could silently fail because the total embed size exceeded Discord's 6,000 character limit. The bot now automatically splits large result sets across multiple embeds (each staying safely under the limit). Each continuation embed is labelled `(cont.)` and a `Part N/M` footer is shown when multiple embeds are sent. A plain-text fallback is also in place if an embed send fails for any reason.

## [2.9.1] - 2026-04-13

### Fixed
- **Ticket search regex** — The search intent now correctly matches natural language patterns where `are open`, `are there`, or `are active` appears between `tickets` and `for`. Previously, phrases like `"what open tickets are open for RLS?"` and `"what tickets are open for RLS?"` fell through to the ticket creation flow (which asked for a subject), because the regex did not account for the verb phrase after `tickets`. The fix adds an optional `(?:are\s+)?(?:open|closed|all|there|active)\s+` group between `tickets?` and the `for/from/of` preposition.

## [2.9.0] - 2026-04-13

### Fixed
- **Time entry note routing** — When a time entry is logged, the note now goes **on the Time Entry only** (visible in CW Time & Expense), not on the ticket Discussion. Previously the note was always posted to the Discussion first, then also passed to the time entry, creating a duplicate.
- **Skip-time flow** — When the user replies `skip` to the "Time to log?" prompt, the note is now correctly posted to the ticket **Discussion** (as before). This ensures notes always land somewhere useful regardless of whether time is logged.
- **Fallback on time entry failure** — If the CW `/time/entries` API call fails, the bot now falls back to posting the note to the Discussion so nothing is lost.
- **Embed field labels** — Confirmation embed now shows `Note on Time Entry` when time is logged, and `Note Added to Discussion` when time is skipped, making it clear where the note landed in ConnectWise.

## [2.8.0] - 2026-04-13

### Added
- **Ticket search feature** — Ask Miles for a company's tickets using natural language:
  - `tickets for [company]` — lists open tickets (default)
  - `open tickets for [company]` — explicitly lists open tickets only
  - `all tickets for [company]` — lists all tickets regardless of status
  - `show tickets for [company]`, `what tickets are open for [company]`, etc.
- **Ticket search results embed** — Each result shows `#TICKET_ID — Subject` as a clickable link directly into ConnectWise, plus the current status badge. Up to 50 tickets per query, sorted newest first.
- **Fuzzy company matching in search** — If the company name isn't recognized exactly, Miles offers up to 3 fuzzy suggestions with a numbered picker (same UX as ticket creation). User picks a number and the search proceeds immediately.
- **`_search_tickets()` method** — Calls `GET /service/tickets` with `company/id=N AND closedFlag=false` (or without the closed filter for all-tickets mode).
- **`_send_ticket_search_results()` async helper** — Builds and sends the Discord embed, handling field chunking for companies with many tickets.
- **`ticket_search_clarify` conversation mode** — Handles the numbered picker follow-up when a company name is ambiguous during a ticket search.

## [2.7.1] - 2026-04-13

### Fixed
- **Work role on time entries** — The bot now extracts a `Work Role:` line from the Discord note, fuzzy-matches it against the ConnectWise work role list, strips it from the note body, and passes the correct `workRoleId` to the `/time/entries` API. Previously, work role was always `null` in ConnectWise regardless of what was typed.

## [2.7.0] - 2026-04-13

### Added
- **Image vision support in assistant mode** — Miles can now read images and screenshots attached to messages in DMs, `#nyc-2026`, and any `@mention` channel. Images are downloaded from Discord, base64-encoded, and passed to Claude's vision API. Supported formats: PNG, JPG, JPEG, GIF, WEBP.
- If only an image is attached with no text, Miles will automatically describe and analyze it.
- Images in `#cw-ticketing` continue to be uploaded directly to ConnectWise tickets (unchanged).

## [2.6.0] - 2026-04-13

### Added
- **Dedicated assistant channels** — Any channel can be configured as a dedicated assistant channel where Miles responds to every message without requiring an `@mention`. The first dedicated channel is `#nyc-2026` (ID `1482497618973032509`). Additional channels can be added to `assistant_channel_ids` in the config file at any time.
- **`assistant_channel_ids` config key** — A new array in `discord_cw_ticket_config.json` that lists channel IDs where Miles operates in full assistant mode for all messages.

## [2.5.0] - 2026-04-12

### Added
- **Dual-mode routing** — Miles now has two distinct personalities based on where you talk to it:
  - **`#cw-ticketing` channel** — ConnectWise only. Creates tickets, logs time, updates tickets. Ignores all non-CW messages.
  - **DMs and `@Miles` in any other channel** — Full conversational assistant with persistent memory.
- **Persistent memory** — A `miles_assistant_memory.json` file is maintained in the OpenClaw memory directory (`/root/.openclaw/SNDayton/memory/`). After each assistant conversation, Claude Haiku extracts new facts and updates a running summary. This memory is injected into every future conversation so Miles remembers context across sessions, days, and reboots.
- **Per-user short-term history** — Each user's last 20 conversation turns are kept in memory during the bot's uptime, giving Miles context within an ongoing conversation.
- **Memory-aware system prompt** — The assistant mode system prompt includes the persistent memory summary and known facts, making Miles context-aware from the first message of any new session.
- **`Miles:` commands work in assistant mode** — All existing `Miles:` / `AI:` prefix commands (summarize, translate, format, etc.) continue to work in DMs and other channels.

## [2.4.0] - 2026-04-12

### Fixed
- **Duplicate bot process** — An orphan instance (PID 2651) started at VPS boot was competing with the systemd-managed instance for Discord gateway messages, causing unpredictable silence. The orphan was killed and the service restarted to ensure a single clean instance.

### Changed
- **Removed single-channel restriction** — The bot previously only responded in the `#cw-ticketing` channel (hard-coded channel ID filter). It now responds in:
  - **Direct Messages (DMs)** to the bot
  - **`#cw-ticketing`** channel (unchanged)
  - **Any channel where `@Miles` is mentioned**
- Messages in other channels without an `@Miles` mention are still ignored to prevent noise.

## [2.3.1] - 2026-04-12

### Fixed
- **`typed_name` extraction** — The clarification prompt was echoing the entire message (e.g., `"Make a new ticket for Buddy Manufacturing"`) instead of just the company name. Lead-in phrases like `"Make a new ticket for"` are now stripped before the name is extracted and displayed.
- **Fuzzy scorer misses near-typos** — The scorer previously required exact substring containment, so `"buddy"` did not match `"budde"`. Added Levenshtein edit-distance scoring: words within 1 edit per 4 characters now score positively. `"Buddy Manufacturing"` now correctly surfaces `"Budde Precision Machining"` as the top suggestion.
- **Added `_edit_distance()` static method** — Pure-Python Levenshtein implementation, no external dependencies.

## [2.3.0] - 2026-04-12

### Added
- **Confidence-based client clarification prompt** — When no client is found after all lookup passes, the bot now presents a numbered list of the top 3 closest fuzzy matches from the ConnectWise company list instead of hard-failing. Example:
  > ❓ I don't recognize "Buddy Manufacturing". Did you mean one of these?
  > `1` Budde Precision Machining
  > `2` BOSS Buckeye Office Services LLC
  > `3` Beavercreek City Schools
  > `4` None of these — the client needs to exist in ConnectWise first. 👉 Add them here
  > *(Reply with a number, or type the correct client name)*
- **Numbered reply handler** — When the user replies with a number, the bot confirms the company and resumes ticket creation without requiring the user to retype their original message. If the user types a name instead of a number, the bot attempts to match it and re-prompts if still unrecognized.
- **`_fuzzy_suggest_clients()` method** — New scoring engine that ranks all companies by character-level substring overlap and word matching to produce relevant suggestions.
- **`_send_client_clarify_prompt()` method** — Centralized prompt builder used by both the one-shot parser path and the conversational flow path.

## [2.2.0] - 2026-04-12

### Changed
- **No-client-found response (Option A, initial)** — Replaced hard-fail red X with an instructional message including a direct link to the New Company form in ConnectWise and instructions to run `Miles: refresh clients`. *(Superseded by v2.3.0 which adds numbered suggestions.)*

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
