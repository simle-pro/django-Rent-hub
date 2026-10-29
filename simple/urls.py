from django.urls import path

from . import views

app_name = 'simple'

urlpatterns = [
    path('search/', views.search, name='search'),
    path('favorites/', views.favorite_list, name='favorite_list'),
    path('favorites/<int:property_id>/toggle/', views.favorite_toggle, name='favorite_toggle'),
    path('bookings/create/<int:property_id>/', views.booking_create, name='booking_create'),
    path('bookings/my/', views.my_bookings, name='my_bookings'),
    path('bookings/received/', views.received_bookings, name='received_bookings'),
    path('bookings/<int:pk>/', views.booking_detail, name='booking_detail'),
    path('bookings/<int:pk>/cancel/', views.booking_cancel, name='booking_cancel'),
    path('bookings/<int:pk>/approve/', views.booking_approve, name='booking_approve'),
    path('bookings/<int:pk>/reject/', views.booking_reject, name='booking_reject'),
]
