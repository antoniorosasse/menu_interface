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
        # 4 cards com fonte: consulta, chat de empresas, proximidade e estatisticas
        self.assertEqual(html.count('class="fontes-linha"'), 4)

    def test_botoes_de_todos_os_cards_ficam_no_rodape(self):
        """Os botoes de cada card vao num bloco .card-acoes no rodape.

        O corpo do card e' coluna flex e o bloco usa margin-top:auto; como os
        cards da mesma linha tem a mesma altura (h-100), o topo dos botoes fica
        alinhado entre o card da esquerda, o do meio e o da direita.
        """
        resp = self.client.get(reverse('core:menu'))
        html = resp.content.decode()
        total = sum(len(secao['projetos']) for secao in resp.context['secoes'])
        self.assertEqual(html.count('d-flex gap-2 card-acoes'), total)
        # CSS que garante o alinhamento
        self.assertIn('.card-acoes {', html)
        self.assertIn('margin-top: auto;', html)
        self.assertIn('flex: 1 1 auto;', html)

    def test_descricao_da_secao_tem_o_mesmo_tamanho_do_titulo(self):
        """A descricao da secao usa o mesmo font-size do titulo (.secao-titulo).

        Antes ficava em 0.82rem e --text-muted, e parecia apagada ao lado do
        titulo em 1.05rem.
        """
        resp = self.client.get(reverse('core:menu'))
        html = resp.content.decode()
        self.assertIn('.secao-desc {', html)
        trecho = html[html.index('.secao-desc {'):]
        trecho = trecho[:trecho.index('}')]
        self.assertIn('font-size: 1.05rem;', trecho)
        self.assertIn('color: var(--text);', trecho)

    # -------------------------------------------------- cards de CNPJ
    def test_menu_mostra_os_quatro_cards_de_cnpj(self):
        resp = self.client.get(reverse('core:menu'))
        html = resp.content.decode()
        for nome in ('Consulta Empresas', 'Chat com IA · Empresas',
                     'Empresas por proximidade', 'Estatísticas da base'):
            with self.subTest(card=nome):
                self.assertIn(nome, html)
        self.assertIn('/proximidade/', html)
        self.assertIn('/estatisticas/', html)

    def test_ordem_dos_cinco_cards_em_destaque(self):
        """4 cards de CNPJ seguidos do card deste site (o 5o em destaque)."""
        resp = self.client.get(reverse('core:menu'))
        secao = resp.context['secoes'][0]
        self.assertEqual(
            [p['id'] for p in secao['projetos']],
            ['cnpj', 'chat_empresas', 'proximidade', 'estatisticas', 'menu'],
        )
        self.assertFalse(secao['compacto'])

    def test_cards_de_ibmi_ficam_na_secao_secundaria(self):
        resp = self.client.get(reverse('core:menu'))
        html = resp.content.decode()
        self.assertIn('Outros projetos em produção (IBM i · DB2)', html)
        self.assertIn('card-compacto', html)
        secundaria = resp.context['secoes'][1]
        self.assertTrue(secundaria['compacto'])
        self.assertEqual([p['id'] for p in secundaria['projetos']], ['as400', 'chat_pessoas'])

    def test_detalhe_de_proximidade_e_estatisticas_respondem_200(self):
        for projeto_id in ('proximidade', 'estatisticas'):
            with self.subTest(projeto=projeto_id):
                resp = self.client.get(reverse('core:detalhe_projeto', args=[projeto_id]))
                self.assertEqual(resp.status_code, 200)

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

