import socket
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from .models import Alert, Incident, Monitor
from .services import UnsafeURL, record_result, run_due_checks, validate_public_url

OK = {"status_code": 200, "response_ms": 80, "is_up": True, "error": "", "ssl_expires_at": None}
FAIL = {"status_code": None, "response_ms": None, "is_up": False, "error": "ConnectionError", "ssl_expires_at": None}


class SSRFTests(TestCase):
    def test_blocks_loopback_private_and_bad_scheme(self):
        for url in ("http://127.0.0.1/", "http://localhost/", "http://10.0.0.5/", "http://169.254.169.254/latest/meta-data/", "ftp://example.com/"):
            with self.assertRaises(UnsafeURL, msg=url):
                validate_public_url(url)

    def test_allows_public_ip(self):
        with patch("pulse.services.socket.getaddrinfo", return_value=[(2, 1, 6, "", ("93.184.216.34", 80))]):
            validate_public_url("http://example.com/")


class RuleTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("sadia", "s@example.com", "pass12345")
        self.m = Monitor.objects.create(owner=self.user, name="Portal", url="https://portal.example.com")

    def test_retry_threshold_incident_and_recovery(self):
        record_result(self.m, FAIL)
        record_result(self.m, FAIL)
        self.assertNotEqual(self.m.status, Monitor.DOWN)       # 2 failures: still not an outage
        self.assertEqual(Incident.objects.count(), 0)
        record_result(self.m, FAIL)                            # 3rd failure
        self.assertEqual(self.m.status, Monitor.DOWN)
        self.assertEqual(Incident.objects.filter(resolved_at__isnull=True).count(), 1)
        self.assertEqual(Alert.objects.filter(kind=Alert.DOWN).count(), 1)
        record_result(self.m, FAIL)                            # still down: no duplicate alert
        self.assertEqual(Alert.objects.filter(kind=Alert.DOWN).count(), 1)
        record_result(self.m, OK)
        self.assertEqual(self.m.status, Monitor.UP)
        self.assertEqual(Incident.objects.filter(resolved_at__isnull=True).count(), 0)
        self.assertEqual(Alert.objects.filter(kind=Alert.RECOVERED).count(), 1)

    def test_ssl_warning_only_once_per_day(self):
        soon = {**OK, "ssl_expires_at": timezone.now() + timedelta(days=5)}
        record_result(self.m, soon)
        record_result(self.m, soon)
        self.assertEqual(Alert.objects.filter(kind=Alert.SSL).count(), 1)

    def test_run_due_checks_uses_thread_pool(self):
        for i in range(5):
            Monitor.objects.create(owner=self.user, name=f"M{i}", url=f"https://m{i}.example.com")
        with patch("pulse.services.check_url", return_value=OK):
            self.assertEqual(run_due_checks(), 6)
        self.assertEqual(Monitor.objects.filter(status=Monitor.UP).count(), 6)
        with patch("pulse.services.check_url", return_value=OK):
            self.assertEqual(run_due_checks(), 0)               # none due until their interval passes


class WebAndApiTests(TestCase):
    def setUp(self):
        self.a = User.objects.create_user("a", "a@x.com", "pass12345")
        self.b = User.objects.create_user("b", "b@x.com", "pass12345")
        self.ma = Monitor.objects.create(owner=self.a, name="A-site", url="https://a.example.com", is_public=True)
        Monitor.objects.create(owner=self.a, name="A-private", url="https://p.example.com")

    def test_pages_render(self):
        self.client.login(username="a", password="pass12345")
        for name, args in [("home", []), ("dashboard", []), ("monitor_add", []), ("alerts", []),
                           ("monitor_detail", [self.ma.pk]), ("status_user", ["a"])]:
            self.assertEqual(self.client.get(reverse(name, args=args)).status_code, 200, name)

    def test_zero_uptime_is_shown_as_zero_not_no_data(self):
        from .models import CheckResult
        CheckResult.objects.create(monitor=self.ma, is_up=False, error="ConnectionError")
        self.assertContains(self.client.get(reverse("home")), "0.0%")

    def test_dashboard_requires_login(self):
        self.assertEqual(self.client.get(reverse("dashboard")).status_code, 302)

    def test_user_cannot_open_anothers_monitor(self):
        self.client.login(username="b", password="pass12345")
        self.assertEqual(self.client.get(reverse("monitor_detail", args=[self.ma.pk])).status_code, 404)
        self.assertEqual(self.client.post(reverse("monitor_delete", args=[self.ma.pk])).status_code, 404)

    def test_public_board_hides_private_monitors(self):
        resp = self.client.get(reverse("home"))
        self.assertContains(resp, "A-site")
        self.assertNotContains(resp, "A-private")

    def test_form_rejects_internal_url(self):
        self.client.login(username="a", password="pass12345")
        resp = self.client.post(reverse("monitor_add"), {"name": "x", "url": "http://127.0.0.1:8000", "interval_seconds": 60})
        self.assertContains(resp, "not allowed")

    def test_api_needs_token_and_isolates_users(self):
        api = APIClient()
        self.assertEqual(api.get("/api/monitors/").status_code, 401)
        api.credentials(HTTP_AUTHORIZATION="Token " + Token.objects.create(user=self.b).key)
        self.assertEqual(api.get("/api/monitors/").json(), [])             # b sees none of a's monitors
        with patch("pulse.serializers.validate_public_url"):
            resp = api.post("/api/monitors/", {"name": "B", "url": "https://b.example.com", "interval_seconds": 60}, format="json")
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(len(api.get("/api/monitors/").json()), 1)

    def test_api_rejects_internal_url(self):
        api = APIClient()
        api.credentials(HTTP_AUTHORIZATION="Token " + Token.objects.create(user=self.a).key)
        resp = api.post("/api/monitors/", {"name": "evil", "url": "http://169.254.169.254/", "interval_seconds": 60}, format="json")
        self.assertEqual(resp.status_code, 400)
