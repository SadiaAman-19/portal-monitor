from django.urls import path

from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("register/", views.register, name="register"),
    path("dashboard/", views.dashboard, name="dashboard"),
    path("monitors/add/", views.monitor_add, name="monitor_add"),
    path("monitors/<int:pk>/", views.monitor_detail, name="monitor_detail"),
    path("monitors/<int:pk>/toggle/", views.monitor_toggle, name="monitor_toggle"),
    path("monitors/<int:pk>/delete/", views.monitor_delete, name="monitor_delete"),
    path("monitors/<int:pk>/check/", views.monitor_check_now, name="monitor_check_now"),
    path("alerts/", views.alerts, name="alerts"),
    path("status/<str:username>/", views.status_user, name="status_user"),
]
