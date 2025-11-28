from django.contrib import admin
from .models import BannerPosition, Banner, BannerPurchase


@admin.register(BannerPosition)
class BannerPositionAdmin(admin.ModelAdmin):
    list_display = ['name', 'position_type', 'get_dimensions', 'price_month', 'is_active', 'has_active_banner']
    list_filter = ['is_active', 'position_type']
    prepopulated_fields = {'slug': ('name',)}
    
    def has_active_banner(self, obj):
        return obj.has_active_banner()
    has_active_banner.boolean = True
    has_active_banner.short_description = 'Bezet'


@admin.register(Banner)
class BannerAdmin(admin.ModelAdmin):
    list_display = ['alt_text', 'destination_url', 'created_at']
    search_fields = ['alt_text', 'destination_url']
    readonly_fields = ['created_at']


@admin.register(BannerPurchase)
class BannerPurchaseAdmin(admin.ModelAdmin):
    list_display = ['position', 'period', 'price_paid', 'status', 'buyer_email', 'start_date', 'end_date', 'days_remaining']
    list_filter = ['status', 'period', 'position']
    search_fields = ['buyer_email', 'buyer_name', 'company_name']
    readonly_fields = ['purchase_id', 'stripe_session_id', 'stripe_payment_intent', 'created_at']
    
    fieldsets = (
        ('Aankoop', {
            'fields': ('purchase_id', 'position', 'banner', 'period', 'price_paid', 'status')
        }),
        ('Datums', {
            'fields': ('start_date', 'end_date', 'created_at')
        }),
        ('Koper', {
            'fields': ('buyer_email', 'buyer_name', 'company_name')
        }),
        ('Stripe', {
            'fields': ('stripe_session_id', 'stripe_payment_intent'),
            'classes': ('collapse',)
        }),
    )
    
    def days_remaining(self, obj):
        return obj.days_remaining()
    days_remaining.short_description = 'Dagen over'
