# /home/neto/menu_interface/core/tests.py
"""
Testes do menu e da pagina de detalhe.

O health check dos apps remotos e mockado: teste nao faz requisicao de rede.
"""
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse

from core.views import FONTES_CEP, FONTES_EMPRESAS, FONTES_IBGE, FONTES_RFB

SAUDE_OK = {'status': 'online', 'code': 200, 'ms': 10, 'erro': None}


class FontesDeDadosTests(TestCase):
    """Cada card declara as bases publicas de onde saem os dados."""

    def setUp(self):
        p = patch('core.views._check_health_deep_cached', return_value=SAUDE_OK)
        p.start()
        self.addCleanup(p.stop)

    # -------------------------------------------------- estrutura
    def test_todas_as_fontes_tem_curto_nome_url_e_obs(self):
        for fonte in FONTES_EMPRESAS:
            with self.subTest(fonte=fonte.get('nome')):
                for chave in ('curto', 'nome', 'url', 'obs'):
                    self.assertTrue(fonte.get(chave), f'{chave} vazio em {fonte}')
                self.assertTrue(fonte['url'].startswith('https://'), fonte['url'])

    def test_sem_url_repetida(self):
        urls = [f['url'] for f in FONTES_EMPRESAS]
        self.assertEqual(len(urls), len(set(urls)), 'fonte duplicada na lista')

    def test_grupos(self):
        self.assertEqual(FONTES_EMPRESAS, FONTES_RFB + FONTES_CEP + FONTES_IBGE)
        # 2 da RFB + 4 de CEP/geo + 1 do IBGE
        self.assertEqual(len(FONTES_RFB), 2)
        self.assertEqual(len(FONTES_CEP), 4)
        self.assertEqual(len(FONTES_IBGE), 1)

    # -------------------------------------------------- card no menu
    def test_menu_mostra_a_fonte_de_cada_card_de_empresas(self):
        resp = self.client.get(reverse('core:menu'))
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode()
        for fonte in FONTES_EMPRESAS:
            self.assertIn(fonte['url'], html)
            self.assertIn(fonte['curto'], html)

    def test_card_sem_fonte_nao_renderiza_a_linha(self):
        """IBM i e o card de demonstracao nao tem base externa: sem 'Dados'."""
        resp = self.client.get(reverse('core:menu'))
        html = resp.content.decode()
        # 2 cards com fonte (cnpj e chat de empresas)
        self.assertEqual(html.count('class="fontes-linha"'), 2)

    # -------------------------------------------------- pagina de detalhe
    def test_detalhe_do_cnpj_lista_todas_as_fontes(self):
        resp = self.client.get(reverse('core:detalhe_projeto', args=['cnpj']))
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode()
        self.assertIn('Fontes de dados', html)
        for fonte in FONTES_EMPRESAS:
            self.assertIn(fonte['nome'], html)
            self.assertIn(fonte['obs'], html)

    def test_detalhe_do_ibmi_nao_tem_secao_de_fontes(self):
        resp = self.client.get(reverse('core:detalhe_projeto', args=['as400']))
        self.assertEqual(resp.status_code, 200)
        self.assertNotIn('Fontes de dados', resp.content.decode())

    def test_detalhe_de_projeto_inexistente_da_404(self):
        resp = self.client.get(reverse('core:detalhe_projeto', args=['nao-existe']))
        self.assertEqual(resp.status_code, 404)

