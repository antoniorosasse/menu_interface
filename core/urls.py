# /home/neto/menu_interface/core/urls.py
from django.urls import path
from . import views

app_name = 'core'

urlpatterns = [
    # A raiz decide pelo Host: landing comercial (busquecnpj.com.br) ou
    # menu/portfolio. O name 'menu' foi mantido para nao quebrar o que
    # ja usa reverse('core:menu') nem a suite de testes.
    path('', views.home, name='menu'),

    # Preview da landing em qualquer host (util no runserver: /site/)
    path('site/', views.landing_comercial, name='landing'),

    path('projeto/<str:projeto_id>/', views.detalhe_projeto, name='detalhe_projeto'),
]
