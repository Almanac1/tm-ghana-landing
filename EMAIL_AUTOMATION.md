# Registration email automation with Celery

Implemented locally; production deployment is still required. No real mail was sent during development or tests.

## What was inspected and retained

The public booking flow is `landing.views` → `email_queue.book()` → linked `Submission`, `Reservation`, and `ClassDate` records. The existing SQL outbox, conditional worker claims, legacy enrollment, cancellation/rescheduling signals, shared `MeetingSettings`, template admin, SMTP configuration and heartbeat model are reused. Synchronous request delivery and standalone polling have been replaced with Celery tasks and Beat.

Actual database template identifiers were inspected:

| Admin name | Identifier | Schedule |
| --- | --- | --- |
| Registration completion | `registration_complete` | Immediately after registration commits |
| 24-hour meeting reminder | `meeting_reminder_24h` | ClassDate start minus 24 hours |
| 1-hour meeting reminder | `meeting_reminder_1h` | ClassDate start minus 1 hour |

Existing template placeholders are `user_first_name`, `session_date`, `session_time`, and `meeting_link`. Compatibility aliases `first_name`, `name`, `user`, `submission`, and `session_type` remain available. Added `participant_name`, `event`, `event_date`, `event_time`, `timezone`, and `session_timezone`. `session_time` includes WAT and Africa/Lagos. Templates can use `user.name` and `submission.name`. Both subject and body are fetched afresh at sending time. Missing templates, invalid syntax, unknown rendered variables, empty subject/body, missing name/email/event and missing meeting link produce visible outbox errors; no fallback silently replaces an admin template. A blank meeting link is retryable for all participant emails. Correct failed template records, then explicitly requeue the affected jobs using the recovery command below.

The locally inspected database had all three templates, **zero active events**, and **no meeting link**. This is not a statement about production. Set the shared meeting link in admin before registering a test participant. There are no event-specific links in this schema; every occurrence uses the current shared link.

## Timing and durability

`ClassDate.starts_at` explicitly interprets date/time in **Africa/Lagos (WAT, UTC+1)**, independently of the viewer's current timezone. Django has `USE_TZ=True` and `TIME_ZONE='Africa/Lagos'`; Celery uses UTC. Outbox deadlines are aware UTC timestamps. Admin displays datetimes in Django's active timezone.

Registration and outbox creation occur in the same transaction, including direct `Submission.save()` creation with an attached active event. A rollback removes the emails and discards the commit callback. `transaction.on_commit()` publishes immediate confirmation/admin job IDs. A broker failure is logged, leaves the rows pending, and does not turn a saved registration into a failed request. A repeated POST uses the existing unique normalized email/event registration and does not replay mail.

Beat publishes a dispatcher every **30 seconds**. The dispatcher reads due SQL records and publishes short tasks containing only row IDs; no long ETA/countdown tasks are used. Losing broker messages or restarting services is recoverable from pending SQL records. Each task conditionally updates `pending` → `sending`; concurrent/redelivered tasks cannot claim an already claimed record. The database constraint is `(submission, occurrence, kind)`. The migration associates existing outbox records with their linked occurrence without scheduling historical mail.

Only future reminder deadlines are created at registration: >24 hours remaining creates both; >1 and <=24 creates the one-hour reminder; <=1 creates none. An exact deadline is already passed for this purpose. Confirmation still queues in every successful registration.

Expected dispatch tolerance with healthy idle services is **0–30 seconds plus broker, worker queue, rendering and SMTP latency**. There is no real-time guarantee. At send time, a reminder may be at most **five minutes late (inclusive)** and must precede event start. Older reminders become `expired`, including after outages; they are not sent together on recovery. Capacity is bounded to 1,000 due IDs per dispatcher pass; scale workers/database capacity for larger volumes and monitor overdue work.

Cancellation of Submission, Reservation, or ClassDate (deactivation) cancels pending jobs. Deleting a ClassDate/Reservation cancels linked work; deleting a Submission cascades its outbox. Saving ClassDate.date/time recalculates unsent reminders, including previously expired/failed reminders when the start changes; sent reminders remain sent. Moving a participant to another ClassDate cancels its old pending records and creates eligible reminder records for the new occurrence. A pending confirmation follows the moved booking; sent confirmations are never replayed. Historical sent flags remain compatible.

Use admin or model `.save()` for schedule/cancellation edits. Bulk SQL / `QuerySet.update()` bypass hooks. Sending tasks recheck current cancellation, occurrence, event time and deadline, but an earlier event moved through bulk SQL cannot be discovered promptly from a later stored deadline. An email already being transmitted cannot be recalled, and a cancellation/reschedule can race with the final network call.

## Attempts and acceptance

There are four automatic transport attempts, with exponential delays of **1, 2, and 4 minutes** for known transient failures (explicit SMTP 4xx rejection, DNS/connection refusal, recipient 4xx, backend returning zero). The deadline/expiry rules still apply on each retry, so a reminder can expire before using all four attempts. Permanent/configuration failures stop visibly. Rows retain attempts, last attempt time, claim time, next attempt, recipient, Message-ID, sent time, provider acceptance timestamp and useful errors. Recipient is set when scheduled and refreshed to the actual recipient before transport.

`sent` / `provider_accepted_at` means **the configured backend accepted the message**, not confirmed inbox delivery. SMTP acceptance does not prove inbox placement; with file/locmem test backends, it means the test backend accepted it. Bounce/delivery webhooks are not implemented.

The configured provider is SMTP (Namecheap Private Email), which has no provider idempotency-key API. A stable Message-ID aids investigation but is not an idempotency guarantee. Disconnects, timeouts, resets, broken pipes and soft task timeouts become `uncertain`; they are not automatically retried. A worker crash while holding a claim becomes uncertain after five minutes. Send tasks have 60-second soft/90-second hard limits on the production prefork worker, below that lease. This conservative policy may require manual recovery even for a crash before transmission. If SMTP accepts a message and the process dies before saving acceptance, delivery is uncertain; manually retrying without checking provider logs can duplicate it. Exactly-once SMTP delivery is not claimed.

Investigate provider logs before resolving failed/uncertain rows:

```bash
python manage.py resolve_email_delivery 123 --accepted --note 'Provider log reference confirms acceptance'
# OR, only if provider logs confirm it was not accepted:
python manage.py resolve_email_delivery 123 --retry --note 'Provider confirms no acceptance; configuration corrected'
```

These commands record a resolution without sending directly. Attempts are preserved; manual retry authorizes an additional attempt if the automatic budget is exhausted. `--accepted` records the operator verification time. Pending work is picked up by Beat.

## Install and run

From the deployed project checkout, activate its Python virtualenv. All processes must use the same configuration and persistent database. Back up the production database first, stop the previous standalone worker and old reminder cron jobs, install and migrate, then reload Django and start worker/Beat. Migrations do not send mail.

```bash
source .venv/bin/activate
python -m pip install -r requirements.txt
python manage.py migrate --noinput
python manage.py check
python manage.py makemigrations --check --dry-run
```

Celery 5.5.3 supports this checkout's Python 3.9 runtime; timezone-data was updated to satisfy Kombu. Environment examples are in `.env.example`; merge values into the existing ignored `.env`, preserving unrelated settings. Credentials must be supplied by environment or this ignored file, and must be shared by web, worker and Beat. The project loads `.env` using its absolute project path. SSL 465 is the existing SMTP default; TLS/port/timeout are now configurable. Do not enable SSL and STARTTLS simultaneously.

For a local Redis broker, with Docker installed and running (separate terminal):

```bash
docker run --name tm-email-redis --publish 127.0.0.1:6379:6379 --volume tm-email-redis:/data redis:7-alpine redis-server --appendonly yes
# For later restarts of this same container:
# docker start --attach tm-email-redis
```

Set `CELERY_BROKER_URL=redis://127.0.0.1:6379/0`. In production use an authenticated private Redis service, or `rediss://` for TLS as required by the service. Retain the database even if the broker is replaced.

Run a continuous worker in a second terminal/service:

```bash
python -m celery -A config worker --loglevel=INFO --concurrency=2
```

Run **exactly one** Beat instance in a third terminal/service:

```bash
python -m celery -A config beat --loglevel=INFO --schedule=./celerybeat-schedule
```

Use the default prefork pool on Linux for the task time limits. If developing on macOS and prefork is unavailable, `--pool=solo` can be used for a controlled local test; it does not enforce the same hard time limits. Beat needs a writable schedule-file directory. SQL rows, not that file, contain individual email deadlines. Do not use worker `-B` in addition to a separate Beat process. Celery documents the [single scheduler requirement](https://docs.celeryq.dev/en/v5.5.3/userguide/periodic-tasks.html).

The repository's ALLOWED_HOSTS and existing operations script identify **PythonAnywhere** as the intended host. No Docker/service/supervisor deployment manifest or authenticated host inventory exists here. Its actual plan, process quota and broker connectivity remain unverified. PythonAnywhere [Always-on tasks](https://help.pythonanywhere.com/pages/AlwaysOnTasks/) require a paid account. Provision continuously supervised worker and Beat processes (separate available slots/services), plus reachable Redis. Do not assume the host supports a local Redis daemon or arbitrary outbound broker connections: verify this with the host/account, or run the broker and Celery services on a host that supports them and can reach the same database. A free sleeping web host, request threads, browser console or hourly/daily cron cannot meet this schedule. CPU quota exhaustion can stop even an Always-on task. For production prefork/concurrency use a shared persistent PostgreSQL database; the default local SQLite database is suitable for development and small single-host installations, not separate ephemeral filesystems.

## Monitoring and recovery

Admin → Scheduled emails exposes type, recipient, deadline, status, attempts, sent time and errors; details also include occurrence, next attempt, claim, acceptance and Message-ID. Submission admin retains the inline status view. Email worker heartbeats contains independent `email_worker` (worker dispatcher/send execution) and `email_scheduler` (actual Beat tick) rows and a stale indicator after 120 seconds. Missing processes are reported by:

```bash
python manage.py email_queue_status --max-age 120
```

Run this after the first 30–60 seconds, then via external monitoring. It exits nonzero for a missing/stale worker or scheduler heartbeat, overdue pending work or failed/uncertain mail. Admin is a status view; it does not start services. A fresh scheduler plus stale worker usually means broker/worker trouble. A fresh worker plus stale scheduler can mean Beat is stopped while previously queued tasks execute.

`python manage.py process_email_queue` now requests a one-off Celery dispatcher; `--loop` fails with instructions to use Beat. Both old `send_session_*_reminders` commands now also request Celery dispatch, never direct SMTP. Disable their previous scheduled entries to avoid redundant publishing. Existing `enroll_legacy_reminders` preview / `--apply` remains opt-in for historical submissions and suppresses historical confirmations; inspect its output before applying.

## Verify all three emails safely

Automated verification uses a separate test database and the locmem backend, including actual Celery task execution with broker publishing mocked:

```bash
python manage.py test --verbosity 1
```

For a staging end-to-end check with real worker/Beat processes, use a separate staging database and **file-based email**, not production participants. In staging's environment for web AND worker:

```dotenv
EMAIL_BACKEND=django.core.mail.backends.filebased.EmailBackend
EMAIL_FILE_PATH=/absolute/writable/path/tm-test-emails
DEFAULT_FROM_EMAIL=sender@example.com
LANDING_ADMIN_EMAIL=admin@example.com
```

Configure Meeting settings with a test meeting URL. Verify the three admin templates. Start Redis, worker and one Beat as above, then create a test occurrence and book against it from Django shell (this bypasses the public form's Wednesday-only date selector):

```bash
python manage.py shell
```

```python
from datetime import timedelta
from zoneinfo import ZoneInfo
from django.conf import settings
from django.utils import timezone
from landing.models import ClassDate
from landing.email_queue import book
assert settings.EMAIL_BACKEND == 'django.core.mail.backends.filebased.EmailBackend'
start = (timezone.now() + timedelta(hours=24, minutes=2)).astimezone(ZoneInfo('Africa/Lagos')).replace(microsecond=0)
event = ClassDate.objects.create(date=start.date(), time=start.time().replace(tzinfo=None))
registration = book(session_date=event.date, name='Email Test', email='email-test@example.com', phone='123')
print('Event ID:', event.pk, 'Registration ID:', registration.pk)
print(list(registration.scheduled_emails.values('kind', 'scheduled_at', 'status')))
```

Use a date with no other active online occurrence; the date-only booking flow rejects ambiguous dates. Expect a confirmation file promptly and a separate existing admin-alert file. After approximately two minutes plus tolerance, the 24-hour reminder file should appear with correct name, Lagos date/time, timezone and meeting URL. Check its `sent` status in admin.

To verify the one-hour reminder without waiting 23 more hours, **after the 24-hour reminder is sent**, reopen shell and reschedule the same occurrence:

```python
from datetime import timedelta
from zoneinfo import ZoneInfo
from django.utils import timezone
from landing.models import ClassDate
# Replace 123 with the Event ID printed above.
event = ClassDate.objects.get(pk=123)
start = (timezone.now() + timedelta(hours=1, minutes=2)).astimezone(ZoneInfo('Africa/Lagos')).replace(microsecond=0)
event.date, event.time = start.date(), start.time().replace(tzinfo=None)
event.save()
```

Expect the one-hour reminder about two minutes later, using the new event details. The sent confirmation and 24-hour reminder must not replay. For a full unchanged-schedule acceptance test, instead set an occurrence >24 hours away, register through the Wednesday public form, and leave services running through both original deadlines. The accelerated test verifies rescheduling too, rather than pretending two minutes equals 24 hours.

Stop/restart worker and Beat before a reminder deadline to verify pending recovery. A restart within five minutes of the deadline sends it; after five minutes it expires. Use separate staging registrations to test cancellation and late-registration rules. The unit suite covers those exact timing boundaries without waiting. File capture verifies application rendering/dispatch only. Verify actual provider acceptance and inbox placement later using an explicitly controlled registration with your own address and SMTP enabled.

## Local completion and deployment boundary

The Celery implementation, migrations and tests are in this checkout. Final local verification: 69 tests passed, Django system check passed, migration drift check passed, dependency consistency check passed, and migrations 0020/0021 were applied to the local database. Celery task discovery and the configured 30-second Beat entry were verified; a live Redis/worker/Beat stack and production SMTP were not exercised here. Production installation/migration, broker provisioning, continuously supervised worker and singleton Beat, host quotas/network access, meeting link/upcoming events and controlled SMTP/inbox verification remain deployment work. No production services were started and no real email was sent.
