from django.contrib import admin
from django.conf import settings
from django.conf.urls.static import static
from django.urls import include, path
from django.views.generic import RedirectView

urlpatterns = [
    path('', RedirectView.as_view(pattern_name='simple:search', permanent=False)),
    path('admin/', admin.site.urls),
    path('simple/', include('simple.urls')),
    path('smuhammad/', include('smuhammad.urls')),
    path('firuz/', include('firuz.urls')),
]

urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
