from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .forms import MonitorForm, RegisterForm
from .models import Incident, Monitor
from .services import check_url, record_result


def home(request):
    q = request.GET.get("q", "").strip()
    monitors = Monitor.objects.filter(is_public=True, is_active=True).select_related("owner")
    if q:
        monitors = monitors.filter(Q(name__icontains=q) | Q(url__icontains=q))
    return render(request, "pulse/home.html", {"monitors": monitors, "q": q})


def register(request):
    form = RegisterForm(request.POST or None)
    if form.is_valid():
        login(request, form.save())
        return redirect("dashboard")
    return render(request, "registration/register.html", {"form": form})


@login_required
def dashboard(request):
    open_incidents = Incident.objects.filter(monitor__owner=request.user, resolved_at__isnull=True).count()
    return render(request, "pulse/dashboard.html",
                  {"monitors": request.user.monitors.all(), "open_incidents": open_incidents})


@login_required
def monitor_add(request):
    form = MonitorForm(request.POST or None)
    if form.is_valid():
        monitor = form.save(commit=False)
        monitor.owner = request.user
        monitor.save()
        messages.success(request, "Monitor added. The first check runs within a few seconds.")
        return redirect("monitor_detail", pk=monitor.pk)
    return render(request, "pulse/monitor_form.html", {"form": form})


@login_required
def monitor_detail(request, pk):
    monitor = get_object_or_404(Monitor, pk=pk, owner=request.user)  # per-user data isolation
    points = list(monitor.results.values("checked_at", "response_ms")[:60])[::-1]
    chart = {"labels": [timezone.localtime(p["checked_at"]).strftime("%H:%M:%S") for p in points],
             "values": [p["response_ms"] for p in points]}
    return render(request, "pulse/monitor_detail.html", {
        "monitor": monitor, "chart": chart,
        "results": monitor.results.all()[:15], "incidents": monitor.incidents.all()[:10],
        "uptime_24h": monitor.uptime(24), "uptime_7d": monitor.uptime(24 * 7)})


@login_required
@require_POST
def monitor_toggle(request, pk):
    monitor = get_object_or_404(Monitor, pk=pk, owner=request.user)
    monitor.is_active = not monitor.is_active
    monitor.save()
    return redirect("monitor_detail", pk=pk)


@login_required
@require_POST
def monitor_delete(request, pk):
    get_object_or_404(Monitor, pk=pk, owner=request.user).delete()
    messages.success(request, "Monitor deleted.")
    return redirect("dashboard")


@login_required
@require_POST
def monitor_check_now(request, pk):
    monitor = get_object_or_404(Monitor, pk=pk, owner=request.user)
    record_result(monitor, check_url(monitor.url))
    return redirect("monitor_detail", pk=pk)


@login_required
def alerts(request):
    items = list(request.user.alerts.select_related("monitor")[:50])
    request.user.alerts.filter(is_read=False).update(is_read=True)
    return render(request, "pulse/alerts.html", {"alerts": items})


def status_user(request, username):
    owner = get_object_or_404(User, username=username)
    monitors = owner.monitors.filter(is_public=True, is_active=True)
    states = [m.status for m in monitors]
    if not states or Monitor.UNKNOWN in states and Monitor.UP not in states and Monitor.DOWN not in states:
        summary, tone = "No status data yet", "unknown"
    elif Monitor.DOWN in states:
        summary, tone = "Some services are down", "down"
    else:
        summary, tone = "All services are running", "up"
    return render(request, "pulse/status_user.html",
                  {"owner": owner, "monitors": monitors, "summary": summary, "tone": tone})
