from datetime import timedelta

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone


class Monitor(models.Model):
    UNKNOWN, UP, DOWN = "unknown", "up", "down"
    STATUS_CHOICES = [(UNKNOWN, "Unknown"), (UP, "Up"), (DOWN, "Down")]

    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="monitors")
    name = models.CharField(max_length=100)
    url = models.URLField(max_length=500)
    interval_seconds = models.PositiveIntegerField(
        default=60, validators=[MinValueValidator(30), MaxValueValidator(3600)])
    is_active = models.BooleanField(default=True)
    is_public = models.BooleanField(default=False, help_text="Show on the public status board")
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=UNKNOWN)
    consecutive_failures = models.PositiveIntegerField(default=0)
    last_checked = models.DateTimeField(null=True, blank=True)
    next_check = models.DateTimeField(default=timezone.now, db_index=True)
    ssl_expires_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.url})"

    def uptime(self, hours=24):
        """Percentage of successful checks in the last `hours`, or None if no data."""
        since = timezone.now() - timedelta(hours=hours)
        qs = self.results.filter(checked_at__gte=since)
        total = qs.count()
        if not total:
            return None
        return round(100 * qs.filter(is_up=True).count() / total, 2)

    def recent_ticks(self, n=48):
        """Last n check outcomes, oldest first. None = no data yet (drawn as an empty tick)."""
        flags = list(self.results.values_list("is_up", flat=True)[:n])[::-1]
        return [None] * (n - len(flags)) + flags

    @property
    def ssl_days_left(self):
        if not self.ssl_expires_at:
            return None
        return (self.ssl_expires_at - timezone.now()).days


class CheckResult(models.Model):
    monitor = models.ForeignKey(Monitor, on_delete=models.CASCADE, related_name="results")
    checked_at = models.DateTimeField(default=timezone.now, db_index=True)
    status_code = models.PositiveIntegerField(null=True, blank=True)
    response_ms = models.PositiveIntegerField(null=True, blank=True)
    is_up = models.BooleanField()
    error = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ["-checked_at"]


class Incident(models.Model):
    """One outage: opened when a monitor goes DOWN, closed when it recovers."""
    monitor = models.ForeignKey(Monitor, on_delete=models.CASCADE, related_name="incidents")
    started_at = models.DateTimeField(default=timezone.now)
    resolved_at = models.DateTimeField(null=True, blank=True)
    reason = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ["-started_at"]

    @property
    def is_open(self):
        return self.resolved_at is None

    @property
    def duration(self):
        return (self.resolved_at or timezone.now()) - self.started_at


class Alert(models.Model):
    DOWN, RECOVERED, SSL = "down", "recovered", "ssl"
    KIND_CHOICES = [(DOWN, "Down"), (RECOVERED, "Recovered"), (SSL, "SSL expiring")]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="alerts")
    monitor = models.ForeignKey(Monitor, on_delete=models.CASCADE, related_name="alerts")
    kind = models.CharField(max_length=10, choices=KIND_CHOICES)
    message = models.CharField(max_length=300)
    created_at = models.DateTimeField(default=timezone.now)
    is_read = models.BooleanField(default=False)

    class Meta:
        ordering = ["-created_at"]
