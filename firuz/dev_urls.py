from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path('admin/', admin.site.urls),
    path('firuz/', include('firuz.urls')),
    path('simple/', include('simple.urls')),
    path('smuhammad/', include('smuhammad.urls')),
]
