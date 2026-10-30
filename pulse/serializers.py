from rest_framework import serializers

from .models import CheckResult, Monitor
from .services import UnsafeURL, validate_public_url


class MonitorSerializer(serializers.ModelSerializer):
    uptime_24h = serializers.SerializerMethodField()

    class Meta:
        model = Monitor
        fields = ("id", "name", "url", "interval_seconds", "is_active", "is_public",
                  "status", "last_checked", "ssl_expires_at", "uptime_24h")
        read_only_fields = ("status", "last_checked", "ssl_expires_at")

    def get_uptime_24h(self, obj):
        return obj.uptime(24)

    def validate_url(self, value):
        try:
            validate_public_url(value)
        except UnsafeURL as exc:
            raise serializers.ValidationError(str(exc))
        return value


class CheckResultSerializer(serializers.ModelSerializer):
    class Meta:
        model = CheckResult
        fields = ("checked_at", "status_code", "response_ms", "is_up", "error")
