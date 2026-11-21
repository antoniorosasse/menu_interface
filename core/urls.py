# /home/neto/menu_interface/core/urls.py
from django.urls import path
from . import views

app_name = 'core'

urlpatterns = [
    # Raiz do site: portfolio. O mesmo processo serve o menu em qualquer
    # Host; a landing comercial saiu daqui e mora no cnpj_interface (/site/).
    # O name 'menu' foi mantido para nao quebrar o que ja usa
    # reverse('core:menu') nem a suite de testes.
    path('', views.home, name='menu'),

    # Preview do portfolio em qualquer host (util no dev).
    path('menu/', views.menu_principal, name='menu_preview'),

    path('projeto/<str:projeto_id>/', views.detalhe_projeto, name='detalhe_projeto'),
]
