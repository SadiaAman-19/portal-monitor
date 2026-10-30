import time

from django.core.management.base import BaseCommand

from pulse.services import run_due_checks


class Command(BaseCommand):
    help = "Background checker: checks all due monitors in parallel using a thread pool."

    def add_arguments(self, parser):
        parser.add_argument("--once", action="store_true", help="Run one round and exit")
        parser.add_argument("--sleep", type=int, default=5, help="Seconds between rounds")

    def handle(self, *args, **opts):
        while True:
            n = run_due_checks()
            self.stdout.write(f"Checked {n} monitor(s)")
            if opts["once"]:
                break
            time.sleep(opts["sleep"])
