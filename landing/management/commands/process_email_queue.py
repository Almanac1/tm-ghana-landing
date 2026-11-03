import time
from django.core.management.base import BaseCommand, CommandError
from django.db import close_old_connections
from landing.email_queue import process_due


class Command(BaseCommand):
    help = "Process durable email outbox once, or poll in a PythonAnywhere Always-on task."

    def add_arguments(self, parser):
        parser.add_argument("--loop", action="store_true")
        parser.add_argument("--interval", type=int, default=30)
        parser.add_argument("--limit", type=int, default=100)

    def handle(self, *args, **options):
        if options["interval"] < 1 or options["limit"] < 1:
            raise CommandError("interval and limit must be positive")
        while True:
            close_old_connections()
            count = process_due(limit=options["limit"])
            self.stdout.write(f"Email queue checked; sent={count}")
            self.stdout.flush()
            if not options["loop"]:
                return
            time.sleep(options["interval"])
