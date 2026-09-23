# /home/neto/menu_interface/menu_project/urls.py
from django.contrib import admin
from django.urls import path, include
from django.http import HttpResponse

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('core.urls', namespace='core')),
    path('health/', lambda r: HttpResponse('ok'), name='health'),
]