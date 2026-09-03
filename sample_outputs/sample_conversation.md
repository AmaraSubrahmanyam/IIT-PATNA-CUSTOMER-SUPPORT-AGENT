# Sample Conversation - AI IT Support Assistant

This transcript was captured by running `scripts/smoke_test.py` against the compiled
LangGraph agent in **rule-based fallback mode** (no LLM API key configured), using the
sample data shipped in `data/`. With an `OPENAI_API_KEY` / `GOOGLE_API_KEY` configured,
the same flows are handled by the LLM (better natural-language understanding and more
fluent phrasing), but the tool calls, state machine and safety checks below are identical.

---

## Scenario 1 - Knowledge Search

> **User:** How do I reset my VPN password?

**Assistant:**
> **How to Reset Your VPN Password**
>
> To reset your VPN password: 1) Go to the company self-service portal at
> portal.company.com/reset. 2) Click 'Forgot Password' under the VPN section. 3) Enter
> your employee email and complete the OTP verification sent to your registered email.
> 4) Set a new password (minimum 12 characters, must include a number and a symbol).
> 5) Restart your VPN client and log in with the new password. If the issue persists
> after 3 attempts, please raise a support ticket.

*(Tool used: `knowledge_search` → KB001)*

---

## Scenario 2 - Ticket Lookup (multi-turn, matches the assignment's example flow)

> **User:** What is the status of my laptop issue?

**Assistant:** I couldn't find any tickets for employee None. *(employee not yet known)*

> **User:** EMP1024

**Assistant:** Thanks, I found your profile: **Emma Watson** (Marketing). Would you like
me to check your existing tickets? (yes/no)

> **User:** Yes.

**Assistant:**
> Here are your tickets:
> - **TCK-1004** [Open] VPN - VPN disconnects randomly every 10 minutes. (Priority: High)
> - **TCK-1001** [In Progress] Hardware - Laptop screen flickering intermittently. (Priority: Medium)

*(Tools used: `employee_lookup` → verified, then `ticket_lookup`)*

---

## Scenario 3 - Ticket Creation (with mandatory confirmation)

> **User:** My VPN is not working, please raise a ticket

**Assistant:**
> I'd like to create the following ticket:
> - Category: VPN
> - Priority: Medium
> - Description: My VPN is not working
>
> Shall I proceed? (yes/no)

> **User:** Yes.

**Assistant:** ✅ Your ticket has been created: **TCK-1006** (VPN, Medium priority, status: Open).

*(Tool used: `create_ticket`; category auto-classified, employee already verified from Scenario 2)*

---

## Scenario 4 - Duplicate Ticket Detection (safety requirement)

> **User:** My VPN is still not working, please raise another ticket

**Assistant:** You already have an open ticket **TCK-1006** that looks similar: "My VPN
is not working" (Status: Open). Would you still like me to create a new ticket anyway? (yes/no)

*(The agent does not silently create a duplicate - it surfaces the existing ticket and asks for confirmation.)*

---

## Scenario 5 - System Status Check

> **User:** Is the WiFi down?

**Assistant:**
> Current system status:
> - **VPN**: Operational - All VPN gateways operating normally.
> - **Email**: Operational - Email services running normally.
> - **WiFi**: Degraded - Intermittent slowness reported on the 3rd floor access points; network team investigating.
> - **Printers**: Operational - All networked printers online.
> - **HR Portal**: Outage - HR portal is currently down for scheduled maintenance until 12:00 PM.

*(Tool used: `system_status_check`. Note: this question arrived while a duplicate-ticket
confirmation was pending - the agent recognised the topic change and answered directly
instead of getting stuck re-asking yes/no.)*

---

## Scenario 6 - General Greeting (no tool required)

> **User:** hello

**Assistant:** I'm here to help with IT support - password resets, checking ticket
status, raising new tickets, or checking system status. What do you need help with?

---

## Scenario 7 - Unknown Employee ID

> **User:** What is the status of my ticket?

**Assistant:** *(returns tickets for the already-verified employee from earlier in the conversation)*

> **User:** EMP9999

**Assistant:** I couldn't find an employee record for that ID. Please double-check your
employee ID (format: EMP1024) and try again.

*(Tool used: `employee_lookup` → not found; the agent never invents an employee profile.)*

---

## Scenario 8 - User Declines Ticket Creation

> **User:** My email is not syncing, please raise a ticket

**Assistant:**
> I'd like to create the following ticket:
> - Category: Email
> - Priority: Medium
> - Description: My email is not syncing
>
> Shall I proceed? (yes/no)

> **User:** No.

**Assistant:** Okay, I won't create the ticket. Let me know if you'd like to try again.

*(No ticket is created - the agent never acts without explicit confirmation.)*
