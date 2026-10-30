from django.urls import include, path
from rest_framework.authtoken.views import obtain_auth_token
from rest_framework.routers import DefaultRouter

from .api_views import MonitorViewSet

router = DefaultRouter()
router.register("monitors", MonitorViewSet, basename="monitor")

urlpatterns = [
    path("token/", obtain_auth_token, name="api_token"),  # POST username+password -> token
    path("", include(router.urls)),
]
