from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from .models import Profile, Poem


class ProfileInline(admin.StackedInline):
    """Profile inline voor User admin - credits direct bij user zichtbaar"""
    model = Profile
    can_delete = False
    verbose_name_plural = 'Profiel'


class UserAdmin(BaseUserAdmin):
    """Uitgebreide User admin met Profile inline"""
    inlines = [ProfileInline]
    list_display = ['username', 'email', 'get_credits', 'is_active', 'date_joined']
    
    def get_credits(self, obj):
        try:
            return obj.profile.credits
        except Profile.DoesNotExist:
            return 0
    get_credits.short_description = 'Credits'


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    """Standalone Profile admin voor snelle credit-aanpassingen"""
    list_display = ['user', 'credits']
    list_editable = ['credits']
    search_fields = ['user__username', 'user__email']
    list_filter = ['credits']


@admin.register(Poem)
class PoemAdmin(admin.ModelAdmin):
    """Poem admin"""
    list_display = ['theme', 'user', 'style', 'created_at']
    list_filter = ['style', 'mood', 'created_at']
    search_fields = ['theme', 'recipient', 'generated_text']
    date_hierarchy = 'created_at'


# Herregistreer User met nieuwe admin
admin.site.unregister(User)
admin.site.register(User, UserAdmin)
