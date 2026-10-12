# TM Nigeria automated email audit

Audit date: October 9, 2026. Scope: the Django project in this workspace, its local configuration/database, isolated automated tests, and four authorized SMTP test messages. Production code, scheduler configuration, and delivery logs were not available for comparison. Findings about the local database do not establish the production database's state.

**Assessment:** SMTP submission works from this environment, but reminder scheduling and failure recovery have confirmed gaps. Passing happy-path tests alone does not establish reliable automated delivery.

## October 12 follow-up: admin date selection

Removed the automatically generated Wednesday booking options. The website now offers only active, upcoming online Wednesday dates stored in the admin; deleting a date removes it from both the list and valid reservation choices. An empty schedule displays an availability message. A regression test verifies that deleting October 21 while keeping October 28, 2026 leaves only October 28 bookable. This resolves E1 for new bookings; existing submissions for dates without a stored class schedule still require administrative review. The original audit results below are historical. Current suite: **40 tests, 33 passed and seven expected failures** for the remaining defects. These fixes are local and have not been deployed.

## Notification inventory

| Notification | Trigger | Destination | Content source |
| --- | --- | --- | --- |
| Administrator registration alert | Successful reservation POST, after saving records | `LANDING_ADMIN_EMAIL` | `landing/templates/landing/emails/admin_submission_notification.txt` |
| Visitor confirmation | After the administrator alert succeeds | Submission email | Admin-managed `registration_complete` template, with built-in fallback |
| 24-hour reminder | Explicit invocation of `send_session_reminders` | Pending online submissions for an active class date | Admin-managed `meeting_reminder_24h` template, with built-in fallback |
| 1-hour reminder | Explicit invocation of `send_session_1h_reminders` | Pending online submissions for an active class date | Admin-managed `meeting_reminder_1h` template, with built-in fallback |

Lead capture alone sends no notification. Registration delivery is synchronous inside the HTTP request. Reminders are management commands; nothing in the repository installs or runs a scheduler. Legacy visitor `.txt` templates are not used by the active delivery paths.

## Verification results

- Original suite: 21 tests passed.
- Added audit suite: 17 tests; nine passed and eight reproduced defects, marked `expectedFailure`.
- Combined suite: **38 tests: 30 passed, eight expected failures, no unexpected failures.** Expected failures are unresolved defects, not successful reliability checks.
- Django system check passed. All local landing migrations are applied.
- Safe checks covered sender/recipient routing, administrator Reply-To, personalized date/time content, all three missing-template fallbacks, malformed template fallbacks, SMTP exception propagation, both reminder boundaries, sequential deduplication, inactive/non-online exclusions, missing meeting links, invalid windows, and retry within the window after a failed reminder.
- Automated tests used an isolated test database and in-memory email backend. Existing submissions and reminder flags were not modified.

Reproduce:

```sh
.venv/bin/python manage.py test --verbosity 1
.venv/bin/python manage.py test landing.test_email_audit --verbosity 2
```

## Live SMTP test

The user authorized `ojikutuoladapo@gmail.com` as the test recipient. All four messages were submitted using the configured SMTP backend and accepted successfully (`send()` returned 1 for each). Their subjects contain **`[TM Nigeria EMAIL AUDIT ad3d174a92]`**.

| Message | SMTP acceptance | Inbox/Spam placement |
| --- | --- | --- |
| Administrator registration alert | Accepted | Awaiting recipient confirmation |
| Visitor confirmation | Accepted | Awaiting recipient confirmation |
| 24-hour reminder | Accepted | Awaiting recipient confirmation |
| 1-hour reminder | Accepted | Awaiting recipient confirmation |

These messages used synthetic contact/session details and a clearly marked example meeting URL. Every recipient was redirected to the authorized inbox. No real booking was created, no administrator inbox was contacted separately, and no production reminder command was run. This verifies template rendering and SMTP submission from this workspace, rather than a production website booking or scheduled execution. SMTP acceptance does not establish delivery or reading.

The first sandboxed attempt failed DNS resolution before sending; the approved network-enabled attempt above succeeded. The script uses a 20-second timeout; the application itself currently has no explicit SMTP timeout.

Live-test script: `scripts/email_audit_live.py`. Running it again sends another four real test emails.

## Confirmed defects

| ID | Priority | Evidence and effect | Recommended correction |
| --- | --- | --- | --- |
| E1 | High | Booking options always include five fallback Wednesdays, even without corresponding `ClassDate` records. Both reminder commands iterate only stored active class dates. A submission on a fallback-only date receives no reminder. Confirmation lookup also returns a raw ISO date and blank time for that date. | Derive booking choices and reminders from one persisted session schedule; require a scheduled time for every selectable date. |
| E2 | High | `_send_submission_emails` sends the administrator alert before calling the visitor sender. An SMTP exception in the first send prevents the confirmation attempt. The view catches the exception and still displays “We’ve emailed your session details.” There is no persisted delivery state or automatic retry for either registration notification. | Track and attempt each message independently, add durable retries, and make the UI accurately describe delivery status. |
| E3 | High | A reminder recipient's SMTP exception escapes the per-recipient loop and aborts the command. The next eligible recipient is never attempted. The failed recipient remains pending, but another run must occur before the window closes. | Record recipient-level errors, continue the batch, and retry pending failures with a defined deadline. |
| E4 | High | The default reminder window is only five minutes. At exactly +5 minutes and later, pending reminders are skipped indefinitely. No catch-up mechanism exists after scheduler downtime, late registration, or a link added after the window. | Query all pending reminders that are due, with an explicit cutoff before the session, and monitor failed/overdue notifications. |
| E5 | Medium | The 24-hour command filters session dates from `now + 24h` forward. Reminder due Jan 1 at 23:58, execution Jan 2 at 00:01, session Jan 2 at 23:58: the date filter excludes the session although execution is within the five-minute window. | Calculate candidate bounds backward from now for overdue reminder windows, preferably using a stored session datetime. |
| E6 | Medium | The 1-hour command has the same forward-date filter issue. Reminder due Jan 1 at 22:58, execution at 23:01, session at 23:58: `now + 1h` is Jan 2 and excludes the Jan 1 session. | Use the same corrected datetime query as the 24-hour command. |
| E7 | Medium | `send_template_email` discards the backend's send count. A zero result is treated as success and the reminder flag becomes true despite no accepted message. | Require an accepted send count and leave delivery pending otherwise. |
| E8 | Medium | A syntactically valid template containing an unknown variable silently renders it blank. The fallback only handles missing templates and syntax errors. A first-name typo loses personalization; a meeting-link typo can remove the joining URL. | Validate required placeholders and rendered content before saving or sending templates. |
| E9 | High | The lead `ui_action=edit` branch accepts hidden payload contact details directly into the session without `LeadCaptureForm` validation. A subsequent reservation sends to an invalid email address. The audit reproduces this through the HTTP flow. | Revalidate contact details server-side at final submission and before storing edited details in the session. |

E4 is established by passing boundary checks documenting the current behavior. At the original audit, E1–E3 and E5–E9 each had a desired-behavior test marked `expectedFailure` in `landing/test_email_audit.py`. Following the October 12 fix, E1's test verifies that unscheduled dates are not bookable; the other seven expected failures remain. Remove those markers when correcting the corresponding behavior.

## Configuration and design findings

**Local readiness:** the SMTP password is present, all three email-template records exist, the shared meeting link is absent/blank, and there are zero upcoming active class dates. Reminders cannot currently run successfully against this local configuration. The password value was not printed or stored in this report.

**SMTP:** the configured backend uses `mail.privateemail.com:465` with SSL, TLS disabled, and the configured account as sender. Four successful SMTP submissions establish that credentials and transport worked at test time. The app opens separate sends synchronously and leaves `EMAIL_TIMEOUT` at `None`, so a slow mail server can delay registration responses or reminder batches. Add a bounded timeout and background delivery.

**Timezone:** `TIME_ZONE` is UTC. Reminder commands interpret class times in the current Django timezone, and email times have no timezone label. If administrators enter Nigerian local times, reminders run one hour later than intended. Confirm the schedule convention, use `Africa/Lagos` or explicit session zones, and label times in emails. This is a configuration risk; administrator intent was not available to verify.

**Duplicate prevention:** rerunning commands sequentially sends each reminder once. The local database is SQLite and reports no `select_for_update` support. Therefore the comment claiming that row locks prevent concurrent duplicate sends does not hold for this database. Django documents that `select_for_update()` has no effect on SQLite: [QuerySet documentation](https://docs.djangoproject.com/en/4.2/ref/models/querysets/#select-for-update). PostgreSQL locking behavior was not tested. Even with row locks, an SMTP acceptance followed by a process failure before the sent flag commits can produce a duplicate on retry. Use a durable delivery queue, appropriate database coordination, and reconciliation for ambiguous sends.

**Session identity:** submissions store a date string rather than a foreign key to a scheduled session. Multiple class records can share a date, and confirmation lookup does not filter `is_active`. A confirmation can select a different time from the active class that drives reminders. Enforce a single bookable session per date or persist the selected session's identity.

**Template editing:** admin forms do not validate Django template syntax, required variables, or rendered subject headers. A line break in a visitor name or rendered subject can cause Django to reject the email header. Add validation and previewing. The built-in confirmation intentionally omits the meeting link and promises later details; `MeetingSettings` help text incorrectly says the link appears in every registration email.

**Operational visibility:** sent flags record reminder send completion only. There are no registration delivery records, attempt counts, message IDs, delivery/bounce events, or overdue alerts. Logs alone cannot reliably reconstruct per-notification delivery. No production scheduler evidence was supplied; absence of scheduler files here does not prove production tasks are absent.

## Production verification still required

1. Confirm receipt and Inbox/Spam placement for all four authorized test messages. Inspect full headers for SPF, DKIM, and DMARC results; no email headers or DNS authentication checks were available in this audit.
2. Verify the production version and configuration, active scheduled sessions, shared meeting link, timezone, and database backend.
3. Inspect the hosting scheduler to establish that both commands execute reliably. A once-per-day task is incompatible with the current five-minute window; actual scheduling must be verified. Do not run these commands on production casually because they contact real registrants.
4. Review production command logs, SMTP provider logs, bounces, and delivery errors. SMTP success from this machine does not establish network access or credentials on the production host.
5. After corrections, complete a controlled website registration and scheduled reminder cycle using the authorized test inbox, including an outage/retry exercise.

The read-only browser check could not access `https://tmnigeria.com`; no live form was submitted. These production checks remain open, and this report does not claim full production end-to-end certification.

## Suggested implementation order

First repair the schedule/booking mismatch, validate final contact details, configure the meeting link, and isolate administrator/visitor sends. Next add durable delivery records, retries, recipient-level batch handling, and correct date-window queries. Then address session identity, timezone labels, template validation, bounded SMTP timeouts, concurrency, and production monitoring. The audit adds evidence and tests; it does not change application behavior or deploy fixes.
