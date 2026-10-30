from django.contrib import admin

from .models import Alert, CheckResult, Incident, Monitor

admin.site.register(Monitor)
admin.site.register(CheckResult)
admin.site.register(Incident)
admin.site.register(Alert)
