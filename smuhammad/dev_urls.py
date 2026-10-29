"""URL только для изолированной разработки smuhammad (аналог simple/dev_urls.py).

Общий server/urls.py пока не загружается из-за simple/views.py, поэтому здесь
подключены firuz (вход, профиль) и smuhammad по тем же префиксам, что и в
server/urls.py. В общий проект этот файл не подключается.
"""
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path('admin/', admin.site.urls),
    path('firuz/', include('firuz.urls')),
    path('smuhammad/', include('smuhammad.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
