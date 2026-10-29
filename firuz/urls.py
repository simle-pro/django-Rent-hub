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
]
