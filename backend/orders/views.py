from django.db import IntegrityError
from rest_framework import mixins, status, viewsets
from rest_framework.response import Response

from .models import Order
from .serializers import OrderSerializer


class OrderViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = OrderSerializer

    def get_queryset(self):
        queryset = Order.objects.prefetch_related("items__product")
        if self.request.user.is_staff:
            return queryset
        return queryset.filter(customer=self.request.user)

    def _existing_order(self, user, key):
        """Look up a previous order placed by this user under this key.

        Extracted so a test can force it to miss, which is the state two
        simultaneous requests are both in before either has committed.
        """
        return Order.objects.filter(customer=user, idempotency_key=key).first()

    def create(self, request, *args, **kwargs):
        key = request.headers.get("Idempotency-Key") or None
        if key is None:
            return super().create(request, *args, **kwargs)

        existing = self._existing_order(request.user, key)
        if existing is not None:
            return Response(self.get_serializer(existing).data, status=status.HTTP_200_OK)

        try:
            return super().create(request, *args, **kwargs)
        except IntegrityError:
            existing = self._existing_order(request.user, key)
            if existing is None:
                raise
            return Response(self.get_serializer(existing).data, status=status.HTTP_200_OK)

    def perform_create(self, serializer):
        serializer.save(
            customer=self.request.user,
            idempotency_key=self.request.headers.get("Idempotency-Key") or None,
        )
