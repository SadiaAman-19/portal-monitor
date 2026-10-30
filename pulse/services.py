"""Core logic: URL safety, one check, the retry/incident rules, and the thread pool.

Design rule: worker threads ONLY do network I/O (check_url). All database writes happen
afterwards in the main thread (record_result). This avoids "database is locked" errors and
keeps the code easy to reason about.
"""
import ipaddress
import socket
import ssl
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone as dt_timezone
from urllib.parse import urlparse

import requests
from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone

from .models import Alert, CheckResult, Incident, Monitor


class UnsafeURL(ValueError):
    pass


def validate_public_url(url):
    """SSRF protection: only http/https, and every resolved IP must be a public address."""
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise UnsafeURL("Only http:// or https:// URLs with a hostname are allowed.")
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    try:
        infos = socket.getaddrinfo(parsed.hostname, port, proto=socket.IPPROTO_TCP)
    except socket.gaierror:
        raise UnsafeURL("This hostname could not be resolved.")
    for info in infos:
        ip = ipaddress.ip_address(info[4][0].split("%")[0])
        if not ip.is_global:
            raise UnsafeURL("Private, loopback, and internal addresses are not allowed.")


def get_ssl_expiry(url):
    parsed = urlparse(url)
    if parsed.scheme != "https":
        return None
    try:
        ctx = ssl.create_default_context()
        with socket.create_connection((parsed.hostname, parsed.port or 443), timeout=5) as sock:
            with ctx.wrap_socket(sock, server_hostname=parsed.hostname) as tls:
                cert = tls.getpeercert()
        return datetime.fromtimestamp(ssl.cert_time_to_seconds(cert["notAfter"]), tz=dt_timezone.utc)
    except Exception:
        return None


def check_url(url):
    """Check one URL. Touches no database, so it is safe to run in many threads."""
    started = time.monotonic()
    try:
        validate_public_url(url)
        # Redirects are NOT followed: a redirect could point to an internal address (SSRF).
        # A 3xx answer still proves the server is alive, so it counts as UP.
        with requests.get(url, timeout=settings.CHECK_TIMEOUT, allow_redirects=False, stream=True,
                          headers={"User-Agent": "CampusPulse/1.0"}) as resp:
            code = resp.status_code
        return {"status_code": code, "response_ms": int((time.monotonic() - started) * 1000),
                "is_up": code < 400, "error": "" if code < 400 else f"HTTP {code}",
                "ssl_expires_at": get_ssl_expiry(url)}
    except UnsafeURL as exc:
        return {"status_code": None, "response_ms": None, "is_up": False, "error": str(exc)[:200],
                "ssl_expires_at": None}
    except requests.RequestException as exc:
        return {"status_code": None, "response_ms": None, "is_up": False,
                "error": type(exc).__name__, "ssl_expires_at": None}


def _alert(monitor, kind, message):
    Alert.objects.create(user=monitor.owner, monitor=monitor, kind=kind, message=message)
    if monitor.owner.email:
        send_mail(f"[CampusPulse] {monitor.name}: {kind}", message, None,
                  [monitor.owner.email], fail_silently=True)


def record_result(monitor, data):
    """Save a check and apply the rules: retry threshold, incidents, alerts, SSL warning."""
    now = timezone.now()
    CheckResult.objects.create(
        monitor=monitor, checked_at=now, status_code=data["status_code"],
        response_ms=data["response_ms"], is_up=data["is_up"], error=data["error"])
    monitor.last_checked = now
    monitor.next_check = now + timedelta(seconds=monitor.interval_seconds)
    if data.get("ssl_expires_at"):
        monitor.ssl_expires_at = data["ssl_expires_at"]

    if data["is_up"]:
        was_down = monitor.status == Monitor.DOWN
        monitor.consecutive_failures = 0
        monitor.status = Monitor.UP
        if was_down:
            incident = monitor.incidents.filter(resolved_at__isnull=True).first()
            if incident:
                incident.resolved_at = now
                incident.save()
                minutes = int(incident.duration.total_seconds() // 60)
                _alert(monitor, Alert.RECOVERED, f"{monitor.name} is back up after {minutes} min.")
    else:
        monitor.consecutive_failures += 1
        # Retry rule: one failed check is not an outage. Declare DOWN only after N in a row.
        if monitor.consecutive_failures >= settings.FAILURE_THRESHOLD and monitor.status != Monitor.DOWN:
            monitor.status = Monitor.DOWN
            reason = data["error"] or "No response"
            Incident.objects.create(monitor=monitor, started_at=now, reason=reason)
            _alert(monitor, Alert.DOWN, f"{monitor.name} is DOWN ({reason}).")

    days = monitor.ssl_days_left
    if days is not None and days <= settings.SSL_WARN_DAYS:
        recent = Alert.objects.filter(monitor=monitor, kind=Alert.SSL, created_at__gte=now - timedelta(days=1))
        if not recent.exists():
            _alert(monitor, Alert.SSL, f"The SSL certificate for {monitor.name} expires in {days} days.")
    monitor.save()


def run_due_checks():
    """Check every active monitor whose time has come, in parallel. Returns how many were checked."""
    due = list(Monitor.objects.filter(is_active=True, next_check__lte=timezone.now()).select_related("owner"))
    if not due:
        return 0
    with ThreadPoolExecutor(max_workers=settings.MAX_WORKERS) as pool:
        results = list(pool.map(lambda m: check_url(m.url), due))
    for monitor, data in zip(due, results):
        record_result(monitor, data)
    return len(due)
