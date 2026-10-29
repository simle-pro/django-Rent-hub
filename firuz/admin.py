from django.contrib import admin

from .models import Profile, Review, PropertyReport


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'role', 'phone']
    list_filter = ['role']
    search_fields = ['user__username', 'phone']


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ['property', 'user', 'rating', 'created_at']
    list_filter = ['rating']
    search_fields = ['property__title', 'user__username', 'text']
    readonly_fields = ['created_at']


@admin.register(PropertyReport)
class PropertyReportAdmin(admin.ModelAdmin):
    list_display = ['property', 'user', 'reason', 'status', 'resolved_by', 'created_at']
    list_filter = ['status', 'reason']
    search_fields = ['property__title', 'user__username', 'text']

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
