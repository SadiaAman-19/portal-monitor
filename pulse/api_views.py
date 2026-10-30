from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import Monitor
from .serializers import CheckResultSerializer, MonitorSerializer
from .services import check_url, record_result


class MonitorViewSet(viewsets.ModelViewSet):
    serializer_class = MonitorSerializer

    def get_queryset(self):
        return Monitor.objects.filter(owner=self.request.user)  # users only ever see their own data

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)

    @action(detail=True, methods=["get"])
    def results(self, request, pk=None):
        monitor = self.get_object()
        return Response(CheckResultSerializer(monitor.results.all()[:100], many=True).data)

    @action(detail=True, methods=["post"])
    def check_now(self, request, pk=None):
        monitor = self.get_object()
        record_result(monitor, check_url(monitor.url))
        return Response(MonitorSerializer(monitor).data)
