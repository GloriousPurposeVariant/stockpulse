from django.contrib import admin
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from inventory.views import ProductViewSet
from orders.views import OrderViewSet

router = DefaultRouter()
router.register("products", ProductViewSet, basename="product")
router.register("orders", OrderViewSet, basename="order")

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/auth/", include("accounts.urls")),
    path("api/v1/", include(router.urls)),
]
