# ConnectWise OpenClaw Bot Roadmap

This document outlines the long-term product vision, planned features, and enhancements for the ConnectWise Discord Bot.

## 🌟 Product Vision: The Specialized ConnectWise Sub-Agent

The ultimate goal of this project is to evolve the bot from a simple parser into a **specialized ConnectWise agent**. 

In the future, this bot will act as a dedicated sub-agent that a "Master Agent" (a general-purpose virtual assistant) can task with ConnectWise-specific operations. The master agent will handle the user's entire day, and when a task involves ConnectWise, it will seamlessly hand off the intent to this specialized agent.

To achieve this, the bot must master **natural language intent matching** — understanding exactly what the user (or master agent) wants to do, mapping it to its own capabilities, and providing constructive feedback when requests are ambiguous.

---

## 💡 Feature Requests & Ideas

We use **GitHub Discussions** to track feature requests and ideas from users. 

If you have an idea for a new feature, a workflow improvement, or a new `Miles:` command:
1. Go to the [Discussions -> Ideas](https://github.com/SuperiorNetworks/connectwise_openclaw-bot-/discussions/categories/ideas) tab
2. Search to see if someone has already suggested it
3. If not, create a new Discussion in the **Ideas** category
4. Vote on other ideas you'd like to see implemented using the 👍 reaction

Ideas that gain traction and fit the project scope will be converted into Issues and added to the Planned Features list below.

---

## 🚀 Planned Features

### Short-Term (Next Release Cycle)

* **Private Self-Hosted Image Hosting for Inline Display**
  * *Description:* Currently, images uploaded via Discord are attached to the ConnectWise ticket's Documents tab. To display images inline within the Discussion note body, the bot needs to upload the image to a private self-hosted server (via FTP, Drive, or GET) and embed the resulting public URL as a markdown image link directly in the note text.
  * *Status:* Gathering requirements (See Discussion #1)

* **Expanded `Miles:` AI Commands**
  * *Description:* Add more built-in AI commands for common MSP tasks, such as `Miles: extract action items`, `Miles: draft client response`, or `Miles: categorize issue`.
  * *Status:* Planned

### Medium-Term

* **Natural Language Improvement & Feedback Loop**
  * *Description:* Improve the bot's ability to match free-form natural language requests with its specific capabilities. If a request is confusing or ambiguous, the bot will provide options to clarify the intent (e.g., "Did you mean to create a ticket, or add a note?"). Once the action is completed, the bot will provide feedback to the user on how to phrase the prompt better next time (e.g., "Next time, you can just say 'add to ticket 12345'"). Users will have a toggle switch to turn this feedback on or off.
  * *Status:* Planned

* **Ticket Status Updates**
  * *Description:* Allow users to change the status of a ticket directly from Discord (e.g., `update ticket 31666 status to In Progress`).
  * *Status:* Planned

* **Time Entry Enhancements**
  * *Description:* Support more complex time entries, including specifying the member, work type, and whether the time is billable or non-billable.
  * *Status:* Planned

### Long-Term / Backlog

* **Interactive Dashboards**
  * *Description:* Daily or weekly summaries of open tickets, SLA warnings, and team performance posted automatically to a designated Discord channel.
  * *Status:* Backlog

* **Multi-Tenant Support**
  * *Description:* Allow a single bot instance to route tickets to different ConnectWise Manage instances based on Discord server or channel configuration.
  * *Status:* Backlog

---

*Note: This roadmap is subject to change based on user feedback and priority shifts. Check the GitHub Issues and Discussions for the most up-to-date status on specific items.*
