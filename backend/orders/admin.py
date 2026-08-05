from django.contrib import admin

from .models import Order, OrderItem


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 1
    autocomplete_fields = ('product',)


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('reference', 'customer', 'status', 'total', 'created_at')
    list_filter = ('status',)
    search_fields = ('reference', 'customer__username')
    readonly_fields = ('reference', 'created_at', 'updated_at')
    list_select_related = ('customer',)
    inlines = (OrderItemInline,)

    def get_queryset(self, request):
        # ``total`` walks order.items, so without this the changelist issues one
        # extra query per row.
        return super().get_queryset(request).prefetch_related('items__product')
