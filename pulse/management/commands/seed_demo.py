from django.contrib.auth.models import User
from django.core.management.base import BaseCommand

from pulse.models import Monitor

DEMO = [
    ("MUET Website", "https://www.muet.edu.pk", True),
    ("HEC Portal", "https://www.hec.gov.pk", True),
    ("Google", "https://www.google.com", True),
    ("Broken API (demo outage)", "https://httpbin.org/status/500", True),
    ("Missing site (demo outage)", "https://this-site-does-not-exist-12345.pk", True),
]


class Command(BaseCommand):
    help = "Creates a demo user (demo / demo12345) with sample monitors for the presentation."

    def handle(self, *args, **opts):
        user, created = User.objects.get_or_create(username="demo", defaults={"email": "demo@example.com"})
        if created:
            user.set_password("demo12345")
            user.save()
        for name, url, public in DEMO:
            Monitor.objects.get_or_create(owner=user, url=url, defaults={
                "name": name, "is_public": public, "interval_seconds": 30})
        self.stdout.write("Demo ready: login demo / demo12345")
