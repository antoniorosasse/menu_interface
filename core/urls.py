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

    # Preview do menu/portfolio em qualquer host. Espelha o /site/: com
    # HOSTS_COMERCIAL=localhost no .env a raiz passa a mostrar a landing,
    # e este caminho continua dando acesso ao portafolio no dev.
    path('menu/', views.menu_principal, name='menu_preview'),

    path('projeto/<str:projeto_id>/', views.detalhe_projeto, name='detalhe_projeto'),
]
