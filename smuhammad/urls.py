from django.urls import path

from . import views

app_name = 'smuhammad'

urlpatterns = [
    path('locations/create/', views.location_create, name='location_create'),
    path('properties/', views.PropertyListView.as_view(), name='property_list'),
    path('properties/my/', views.MyPropertiesListView.as_view(), name='my_properties'),
    path('properties/create/', views.PropertyCreateView.as_view(), name='property_create'),
    path('properties/<int:pk>/', views.PropertyDetailView.as_view(), name='property_detail'),
    path('properties/<int:pk>/edit/', views.PropertyUpdateView.as_view(), name='property_edit'),
    path('properties/<int:pk>/delete/', views.PropertyDeleteView.as_view(), name='property_delete'),
    path('properties/<int:pk>/submit/', views.submit_property, name='property_submit'),
    path('properties/<int:pk>/hide/', views.hide_property, name='property_hide'),
    path('properties/<int:pk>/images/', views.property_images, name='property_images'),
    path('properties/<int:pk>/images/add/', views.add_property_images, name='property_images_add'),
    path(
        'properties/images/<int:pk>/delete/',
        views.delete_property_image,
        name='property_image_delete',
    ),
]
