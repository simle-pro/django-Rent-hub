from django.contrib import admin

from .models import Booking, Favorite


@admin.register(Favorite)
class FavoriteAdmin(admin.ModelAdmin):
    list_display = ['user', 'property', 'created_at']
    list_filter = ['created_at']
    search_fields = ['user__username']


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ['user', 'property', 'start_date', 'end_date', 'status', 'created_at']
    list_filter = ['status']
    search_fields = ['user__username', 'property__title']
