from django.urls import path

from . import views

app_name = 'firuz'

urlpatterns = [
    path('', views.profile, name='home'),
    path('accounts/register/', views.register_user, name='register'),
    path('accounts/login/', views.login_user, name='login'),
    path('accounts/logout/', views.logout_user, name='logout'),
    path('accounts/activate/<uidb64>/<token>/', views.activate, name='activate'),
    path('accounts/profile/', views.profile, name='profile'),
    path('accounts/profile/edit/', views.profile_edit, name='profile_edit'),
    path('accounts/users/<int:pk>/', views.public_profile, name='public_profile'),
    path('reviews/', views.review_list, name='review_list'),
    path('reviews/property/<int:property_id>/', views.property_reviews, name='property_reviews'),
    path('reviews/create/<int:property_id>/', views.review_create, name='review_create'),
    path('reviews/<int:pk>/delete/', views.review_delete, name='review_delete'),
    path('moderation/properties/', views.pending_properties, name='pending_properties'),
    path('moderation/properties/<int:pk>/approve/', views.property_approve, name='property_approve'),
    path('moderation/properties/<int:pk>/reject/', views.property_reject, name='property_reject'),
    path('moderation/reports/create/<int:property_id>/', views.report_create, name='report_create'),
    path('moderation/reports/', views.property_reports, name='property_reports'),
    path('moderation/reports/<int:pk>/resolve/', views.report_resolve, name='report_resolve'),
]
