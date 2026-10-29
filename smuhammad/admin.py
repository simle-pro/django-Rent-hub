from django.contrib import admin

from .models import Amenity, Location, Property, PropertyCategory, PropertyImage


@admin.register(PropertyCategory)
class PropertyCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'description')
    search_fields = ('name',)


@admin.register(Location)
class LocationAdmin(admin.ModelAdmin):
    list_display = ('city', 'address')
    search_fields = ('city', 'address')


@admin.register(Amenity)
class AmenityAdmin(admin.ModelAdmin):
    list_display = ('name',)
    search_fields = ('name',)


class PropertyImageInline(admin.TabularInline):
    model = PropertyImage
    extra = 0


@admin.register(Property)
class PropertyAdmin(admin.ModelAdmin):
    list_display = ('title', 'owner', 'price', 'category', 'location', 'status', 'created_at')
    list_filter = ('status', 'category', 'location')
    search_fields = ('title', 'description', 'owner__username')
    readonly_fields = ('created_at', 'updated_at')
    inlines = (PropertyImageInline,)
    fieldsets = (
        (None, {'fields': ('owner', 'title', 'description', 'price')}),
        ('Связи', {'fields': ('category', 'location', 'amenities')}),
        ('Модерация', {'fields': ('status', 'moderation_reason')}),
        ('Даты', {'fields': ('created_at', 'updated_at')}),
    )
