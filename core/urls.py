# /home/neto/menu_interface/core/urls.py
from django.urls import path
from . import views

app_name = 'core'

urlpatterns = [
    path('', views.menu_principal, name='menu'),
    path('projeto/<str:projeto_id>/', views.detalhe_projeto, name='detalhe_projeto'),
]
