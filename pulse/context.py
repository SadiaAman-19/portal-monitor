def unread_alerts(request):
    """Adds the unread alert count to every template (shown in the navbar)."""
    if request.user.is_authenticated:
        return {"unread_alert_count": request.user.alerts.filter(is_read=False).count()}
    return {}
