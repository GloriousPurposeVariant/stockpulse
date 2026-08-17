from django.contrib import admin

from .models import Product, StockMovement


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('sku', 'name', 'price', 'quantity', 'updated_at')
    search_fields = ('sku', 'name')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(StockMovement)
class StockMovementAdmin(admin.ModelAdmin):
    list_display = ('product', 'delta', 'reason', 'created_at')
    list_filter = ('reason',)
    search_fields = ('product__sku', 'product__name')
    readonly_fields = ('product', 'delta', 'reason', 'created_at')

    # The ledger is append-only, and the only thing allowed to append to it is
    # the code that adjusts Product.quantity in the same transaction. Editing a
    # movement by hand would leave the cached quantity describing a history that
    # no longer exists.
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
