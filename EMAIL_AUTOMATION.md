# TM Nigeria reservation email deployment

Implemented locally November 2, 2026. No production deployment, account change, or live email test was performed. Tests use Django's in-memory backend and a separate test database.

## Inspection and scheduler choice

The reservation form previously saved an unrelated Reservation and Submission, then synchronously sent the administrator alert before the visitor confirmation. Failure of the first email blocked the second. Existing reminder commands looked for date strings in a five-minute window and relied on row locks that SQLite does not implement. No scheduler installation was present in the repository. The default database is SQLite, optionally PostgreSQL; the WSGI module starts only Django. The old timezone was UTC, although the sessions use Nigerian wall-clock times. Existing admin-managed EmailTemplate records and shared MeetingSettings are reused.

PythonAnywhere capabilities were checked against its official documentation on November 2, 2026:

- [Always-on tasks](https://help.pythonanywhere.com/pages/AlwaysOnTasks/): paid accounts; the host restarts the process after failures/maintenance. Confirm an unused task slot on your own account.
- [Scheduled tasks](https://help.pythonanywhere.com/pages/ScheduledTasks): paid accounts support hourly/daily tasks. Older free accounts have one daily task; newer free accounts have none. Hourly tasks cannot provide 30-second reminder precision; a daily task cannot meet this requirement.
- [API](https://help.pythonanywhere.com/pages/API/): authenticated read-only task inventory is available.

**Your actual subscription, available task quota, deployment paths, and production SMTP reachability are unverified.** This workspace has no authenticated connection to the PythonAnywhere account. The worker below is ready for a paid account with an available Always-on slot. Verify that prerequisite before enabling it. If the account is free, upgrading to a plan with Always-on capability is required for this deployment approach. A browser console or web-process thread is not a durable substitute. An external scheduler would require a separately designed authenticated trigger; none is exposed by this change.

## Behavior and data

- A successful booking atomically saves the linked Reservation, Submission, and ScheduledEmail rows. One normalized email address per selected ClassDate is enforced through a unique registration key. Repeated submissions return the existing booking and do not replay emails. A cancelled booking stays cancelled until an administrator reactivates it.
- Confirmation is attempted immediately **after commit**, before the HTTP request finishes. The admin alert is independent and also tracked. Failed/unfinished immediate dispatch stays in the database for the worker. With SMTP timeout 20 seconds, a slow provider can delay the request; no background thread is spawned inside WSGI.
- Session date and time are combined explicitly in `Africa/Lagos` (WAT, UTC+1). Django uses aware datetimes and stores them in UTC. Email times include the zone. Changing Django's current timezone cannot change session interpretation.
- Reminders are persisted at session start minus 24 hours and minus one hour. At registration, only strictly future reminder times are queued. At the exact due boundary, that reminder is omitted for a new registration.
- The existing date-only form is retained. Dates with multiple active online times are excluded instead of choosing an arbitrary session. Configure one active online ClassDate per bookable Wednesday.
- Cancel using **Reservation > is_cancelled**, **Submission > is_cancelled**, or deactivate the ClassDate. Pending emails are cancelled. Deleting a ClassDate or Reservation cancels pending emails and retains Submission/email records. Deleting a Submission cascades its email records.
- Change ClassDate.date/time to reschedule everyone; change Submission.class_date or Reservation.session_date to move an individual. Pending reminders are recalculated, elapsed times cancelled, and sent reminders/confirmations never replayed. Editing Submission.class_date also updates the linked Reservation date. Linking a historical submission never replays its confirmation. Save through admin or model `.save()`; raw SQL, `bulk_update`, and `QuerySet.update` bypass scheduling hooks. The worker rechecks availability and schedule before sending, but cannot discover an earlier reschedule promptly if hooks were bypassed.
- ScheduledEmail records original/current scheduled time, next attempt, session time, state, sent time, claim time, attempts, error, and stable Message-ID. View them under **Scheduled emails**, or within each Submission. **Email worker heartbeats** shows the last completed poll. Legacy reminder flags are read-only compatibility indicators; historical enrollment honors them when creating missing jobs.

## Delivery guarantees and retry policy

Conditional database UPDATE claims prevent two workers from sending the same pending row, including with SQLite. SMTP runs outside database transactions. A unique `(submission, kind)` constraint prevents duplicate queue entries. The normal policy is four dispatch attempts total with delays of 1, 2, and 4 minutes after temporary failure. Explicit SMTP 4xx rejections, temporary single-recipient refusals, DNS failures, connection refusal, missing meeting link, and a backend returning zero are retryable. SMTP 5xx/permanent or other non-transient errors fail visibly. One recipient's failure never stops the batch.

An SMTP disconnect, timeout, reset, or broken pipe can occur after acceptance. Such messages become **uncertain**, with no automatic resend. A process killed while sending leaves a claim; after five minutes another worker marks it uncertain. This prevents automatic duplicates at the cost of requiring provider-log review for these messages. A crash before actual sending can also need that review. SMTP cannot provide both guaranteed delivery and exactly-once acceptance without a provider idempotency API. A stable Message-ID assists investigation but does not force SMTP recipient deduplication.

An email already in flight cannot be recalled when a booking is cancelled or rescheduled. Pending work and not-yet-started dispatches are protected. A session which has started never receives a reminder, including on retry. After an outage, due reminders catch up until session start, so a delayed reminder's template wording ("tomorrow" / "in 1 hour") can be approximate. Sent means the backend/SMTP accepted it, not that it reached an inbox; bounces and SPF/DKIM/DMARC remain provider concerns.

At the default 30-second interval, expected dispatch delay is roughly **0–30 seconds plus batch processing/SMTP latency**, not a real-time guarantee. Each batch handles at most 100 jobs; CPU throttling, maintenance, network outages, large backlogs, and SQLite contention increase delay. Use one Always-on worker for this site's expected volume. Host restarts recover pending work from the same database.

## Exact PythonAnywhere setup

1. In **Account**, verify a paid subscription. In **Tasks**, verify an available **Always-on tasks** slot. Record the project source directory and virtualenv path shown on **Web**. Do not guess those paths from this Mac workspace.

   Optional read-only inventory, run in a new PythonAnywhere Bash console after generating an API token in Account > API Token:

   ```bash
   python scripts/pythonanywhere_email_capabilities.py
   # EU accounts:
   python scripts/pythonanywhere_email_capabilities.py --host eu.pythonanywhere.com
   ```

   Run from the deployed project directory. The script reads PythonAnywhere's `API_TOKEN` environment variable without printing it. API listing success alone does not prove unused task quota; the Account/Tasks check is still required. No API token is needed by the email worker.

2. Upload/pull these changes into the deployed checkout. Open a Bash console in the project directory and activate the **same virtualenv used by Web** (`workon YOUR_ENV`, or `source /absolute/virtualenv/bin/activate`). The commands below derive actual paths from there:

   ```bash
   export TM_PROJECT_DIR="$PWD"
   export TM_PYTHON="$(command -v python)"
   test -f "$TM_PROJECT_DIR/manage.py"
   "$TM_PYTHON" -m pip install -r "$TM_PROJECT_DIR/requirements.txt"
   "$TM_PYTHON" "$TM_PROJECT_DIR/manage.py" check
   "$TM_PYTHON" "$TM_PROJECT_DIR/manage.py" test --verbosity 1
   ```

3. Set SMTP credentials in the project's ignored `.env`, or in an environment configuration shared by **both Web and Tasks**. The project loads `.env` by absolute BASE_DIR for every invocation, independently of working directory. Keep its existing unrelated entries. Required values:

   ```dotenv
   EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
   EMAIL_HOST=mail.privateemail.com
   EMAIL_HOST_USER=your-authorized-sender@tmnigeria.com
   EMAIL_HOST_PASSWORD=your-privateemail-password
   DEFAULT_FROM_EMAIL=your-authorized-sender@tmnigeria.com
   LANDING_ADMIN_EMAIL=your-admin-inbox@tmnigeria.com
   ```

   The configured transport remains SSL port 465 with a 20-second timeout. No credential value is committed. EMAIL_HOST_USER no longer has a hardcoded account fallback: explicitly add it to the production environment. Protect the file:

   ```bash
   chmod 600 "$TM_PROJECT_DIR/.env"
   ```

4. Back up the deployed database before migration using the host's normal database backup procedure. Apply migrations, which **do not enqueue historical emails**:

   ```bash
   "$TM_PYTHON" "$TM_PROJECT_DIR/manage.py" migrate --noinput
   "$TM_PYTHON" "$TM_PROJECT_DIR/manage.py" makemigrations --check --dry-run
   ```

   In admin, review the three existing Email templates, the shared Meeting settings link, and active upcoming Class dates. Enter session times in Lagos local time. Invalid template syntax or unknown variables uses the built-in fallback and logs the problem. Review old schedule values because interpreting existing times as Lagos is an intentional change from the old UTC behavior.

5. Historical submissions have no dependable session foreign key or Reservation link. They are left untouched initially. Preview enrollment and review ambiguous/duplicate records:

   ```bash
   "$TM_PYTHON" "$TM_PROJECT_DIR/manage.py" enroll_legacy_reminders
   ```

   After reviewing, the following explicitly enrolls uniquely matched future sessions; it suppresses historical confirmations/admin alerts and honors existing sent flags:

   ```bash
   "$TM_PYTHON" "$TM_PROJECT_DIR/manage.py" enroll_legacy_reminders --apply
   ```

   This queues real upcoming participant reminders; do it only as part of your intended production rollout. Unmatched/ambiguous/duplicate submissions are reported for manual review. Historical Reservation/Submission pairings cannot safely be inferred: link known pairs in Submission admin, or cancel historical bookings through Submission. Repeated enrollment is idempotent.

6. Disable the **old** scheduler entries for `send_session_reminders` and `send_session_1h_reminders`. Both commands now delegate to the persisted queue without the old five-minute window; no implicit historical enrollment occurs. Do not run the obsolete code in another checkout against the production database.

   Generate the exact Always-on command from the deployed checkout/virtualenv:

   ```bash
   "$TM_PYTHON" -c 'import pathlib, shlex, sys; print(shlex.join([sys.executable, "-u", str(pathlib.Path("manage.py").resolve()), "process_email_queue", "--loop", "--interval", "30", "--limit", "100"]))'
   ```

   Copy its printed line into **Tasks > Always-on tasks > command**. Click **Create** and confirm **Running**. It will look like:

   ```text
   /home/YOUR_USERNAME/.virtualenvs/YOUR_ENV/bin/python -u /home/YOUR_USERNAME/YOUR_PROJECT/manage.py process_email_queue --loop --interval 30 --limit 100
   ```

   These example placeholders are not claimed to be your account's real paths; the generator prints those exactly. No Redis, Celery broker, APScheduler, crontab, or extra package is required. Reload the web app on **Web** after migration/configuration. Web and worker must point to the same checkout, database, and `.env`.

7. Verify after the worker completes its first poll:

   ```bash
   "$TM_PYTHON" "$TM_PROJECT_DIR/manage.py" email_queue_status --max-age 120
   ```

   This is read-only and exits nonzero for missing/stale heartbeat, overdue pending work, failed or uncertain sends. The Tasks log should regularly show `Email queue checked; sent=...`. View the Always-on task's log using its log button; confirm heartbeat progression over multiple polls. Restart the task once and verify progression resumes. Admin and this command only display status; they do not run the scheduler. Production SMTP connectivity and inbox delivery still require a deliberately controlled registration using your own test address after deployment.

## Failure recovery

Inspect Scheduled emails.error, attempts, and Message-ID and consult provider logs. Correct credentials/meeting link/configuration first. Pending transient jobs retry automatically. For failed or uncertain jobs, use a specific record ID with investigation evidence (the command itself never sends):

```bash
python manage.py resolve_email_delivery 123 --accepted --note 'Provider log confirms acceptance; reference ABC'
python manage.py resolve_email_delivery 123 --retry --note 'Provider log confirms no acceptance; configuration fixed'
```

Choose one resolution, not both. `--accepted` records the operator's verification time as sent_at; consult provider logs for the actual historical acceptance time. `--retry` requeues while preserving attempts. If the four-attempt budget was exhausted it authorizes one additional dispatch; further failures stop again. Retrying an uncertain message without verifying non-acceptance can duplicate it. Cancellation/session-start checks still apply to manually requeued jobs.

## Local verification

```bash
.venv/bin/python manage.py test --verbosity 1
.venv/bin/python manage.py check
.venv/bin/python manage.py makemigrations --check --dry-run
```

Final local verification: **55 tests passed**, Django system check passed, migration drift check passed, and migrations 0018/0019 were applied to the local database. No upcoming active sessions or shared meeting link are configured locally; these are not observations about production.

The suite covers the full HTTP booking flow, post-commit confirmation, saved templates, both reminder boundaries, Lagos independent of the current timezone, late registrations, cancellations/deletion, session/individual rescheduling, rollback, temporary/permanent failures, retry limits, zero send count, independent administrator failures, overlapping claims, repeated POSTs, persisted-queue restart/catch-up, expired reminders, missing links, uncertain SMTP/crashed claims, legacy enrollment, and heartbeat health. Tests never send to real participants. The original audit's expected-failure tests have been replaced by passing regressions for the repaired workflow; obsolete five-minute-window expectations were intentionally removed. The standalone live SMTP audit script is not part of this test suite and was not run.
