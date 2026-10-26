"""
test_parked_detector.py - Unit test suite for parked_detector.py

Covers:
1. HTML cleaning and metadata extraction.
2. Parked domain detection (GoDaddy, Hostinger, Registro.br, Locaweb, HostGator, KingHost, UOL, Sedo, Dan.com, etc.).
3. Server default pages (Nginx, Apache, cPanel/WHM, IIS, LiteSpeed, Index of /).
4. Abandoned / Default CMS installations (WordPress taglines, Hello World, Joomla, Drupal).
5. Suspended accounts and expired domains.
6. Under construction and maintenance pages.
7. False positive protection (Civil construction, Auto mechanics, HVAC maintenance, IT maintenance).
8. Blank and short pages (< 80 chars).
9. Schema compliance and edge case input handling.
"""

import unittest
from parked_detector import (
    CATEGORY_BLANK_PAGE,
    CATEGORY_CMS_DEFAULT,
    CATEGORY_NONE,
    CATEGORY_PARKED_DOMAIN,
    CATEGORY_SERVER_DEFAULT,
    CATEGORY_SUSPENDED,
    CATEGORY_UNDER_CONSTRUCTION,
    clean_html_text,
    detect_parked_or_abandoned_site,
    extract_headings,
    extract_html_title,
)


class TestHTMLCleaningAndExtraction(unittest.TestCase):
    """Tests for HTML parsing, sanitization, and text extraction."""

    def test_clean_html_text_strips_scripts_and_styles(self):
        raw_html = """
        <html>
            <head>
                <style>body { color: red; } .hidden { display: none; }</style>
                <script>var x = "should not appear"; alert(x);</script>
            </head>
            <body>
                <h1>Título Principal</h1>
                <p>Conteúdo textual legível.</p>
                <noscript><p>Habilite javascript</p></noscript>
                <svg><text>SVG Vector</text></svg>
            </body>
        </html>
        """
        cleaned = clean_html_text(raw_html)
        self.assertIn("Título Principal", cleaned)
        self.assertIn("Conteúdo textual legível.", cleaned)
        self.assertNotIn("should not appear", cleaned)
        self.assertNotIn("color: red", cleaned)
        self.assertNotIn("Habilite javascript", cleaned)
        self.assertNotIn("SVG Vector", cleaned)

    def test_clean_html_text_unescapes_entities(self):
        raw_html = "<p>Constru&ccedil;&atilde;o &amp; Manuten&ccedil;&atilde;o &#39;Brasil&#39; &quot;Top&quot;</p>"
        cleaned = clean_html_text(raw_html)
        self.assertEqual(cleaned, "Construção & Manutenção 'Brasil' \"Top\"")

    def test_clean_html_text_handles_empty_and_whitespace(self):
        self.assertEqual(clean_html_text(""), "")
        self.assertEqual(clean_html_text(None), "")
        self.assertEqual(clean_html_text("   \n\t   "), "")
        self.assertEqual(clean_html_text("<!-- A comment -->"), "")

    def test_extract_html_title(self):
        html_with_title = "<html><head><title>  Oficina Mec&acirc;nica Silva - S&atilde;o Paulo  </title></head></html>"
        self.assertEqual(extract_html_title(html_with_title), "Oficina Mecânica Silva - São Paulo")
        self.assertEqual(extract_html_title("<html><body>No title here</body></html>"), "")
        self.assertEqual(extract_html_title(""), "")
        self.assertEqual(extract_html_title(None), "")

    def test_extract_headings(self):
        html_with_headings = """
        <html><body>
            <h1>Primeiro Título</h1>
            <p>Texto intermediário</p>
            <h2>Segundo Título &amp; Detalhes</h2>
        </body></html>
        """
        headings = extract_headings(html_with_headings)
        self.assertEqual(len(headings), 2)
        self.assertEqual(headings[0], "Primeiro Título")
        self.assertEqual(headings[1], "Segundo Título & Detalhes")


class TestParkedDomainDetection(unittest.TestCase):
    """Tests for parked domain detection across multiple providers."""

    def test_godaddy_parked_page(self):
        html = """
        <!DOCTYPE html>
        <html><head><title>exemplo.com.br</title></head>
        <body>
            <h1>Parked FREE, courtesy of GoDaddy.com</h1>
            <p>This Web page is parked FREE, courtesy of GoDaddy.</p>
        </body></html>
        """
        result = detect_parked_or_abandoned_site(html)
        self.assertTrue(result["is_parked_or_abandoned"])
        self.assertEqual(result["category"], CATEGORY_PARKED_DOMAIN)
        self.assertIn("GoDaddy", result["reason"])
        self.assertGreaterEqual(result["confidence"], 0.90)

    def test_godaddy_url_redirect(self):
        result = detect_parked_or_abandoned_site("<html><body>Redirecting...</body></html>", url="https://www.godaddy.com/park/exemplo.com")
        self.assertTrue(result["is_parked_or_abandoned"])
        self.assertEqual(result["category"], CATEGORY_PARKED_DOMAIN)
        self.assertIn("GoDaddy", result["reason"])

    def test_hostinger_parked_page(self):
        html = """
        <!DOCTYPE html>
        <html><head><title>Default Web Site Page - Hostinger</title></head>
        <body>
            <h1>Hostinger Domain Parking</h1>
            <p>Este domínio está hospedado na Hostinger.</p>
        </body></html>
        """
        result = detect_parked_or_abandoned_site(html)
        self.assertTrue(result["is_parked_or_abandoned"])
        self.assertEqual(result["category"], CATEGORY_PARKED_DOMAIN)
        self.assertIn("Hostinger", result["reason"])

    def test_registro_br_placeholder(self):
        html = """
        <!DOCTYPE html>
        <html><head><title>Registro.br - Domínio registrado</title></head>
        <body>
            <h1>Domínio registrado por Registro.br</h1>
            <p>Este domínio está registrado no Registro.br e está aguardando publicação de conteúdo.</p>
        </body></html>
        """
        result = detect_parked_or_abandoned_site(html)
        self.assertTrue(result["is_parked_or_abandoned"])
        self.assertEqual(result["category"], CATEGORY_PARKED_DOMAIN)
        self.assertIn("Registro.br", result["reason"])

    def test_locaweb_placeholder(self):
        html = """
        <!DOCTYPE html>
        <html><head><title>Página em Construção - Hospedagem Locaweb</title></head>
        <body>
            <h1>Página em construção - Hospedagem Locaweb</h1>
            <p>Acesse locaweb.com.br/painel para publicar seu site na web.</p>
        </body></html>
        """
        result = detect_parked_or_abandoned_site(html)
        self.assertTrue(result["is_parked_or_abandoned"])
        self.assertEqual(result["category"], CATEGORY_PARKED_DOMAIN)
        self.assertIn("Locaweb", result["reason"])

    def test_hostgator_placeholder(self):
        html = """
        <!DOCTYPE html>
        <html><head><title>HostGator - Página de Espera</title></head>
        <body>
            <h1>HostGator Domain Parking</h1>
            <p>Aguardando publicação no HostGator.</p>
        </body></html>
        """
        result = detect_parked_or_abandoned_site(html)
        self.assertTrue(result["is_parked_or_abandoned"])
        self.assertEqual(result["category"], CATEGORY_PARKED_DOMAIN)
        self.assertIn("HostGator", result["reason"])

    def test_kinghost_placeholder(self):
        html = """
        <html><head><title>Página padrão da KingHost</title></head>
        <body><p>Domínio registrado na KingHost com sucesso.</p></body></html>
        """
        result = detect_parked_or_abandoned_site(html)
        self.assertTrue(result["is_parked_or_abandoned"])
        self.assertEqual(result["category"], CATEGORY_PARKED_DOMAIN)
        self.assertIn("KingHost", result["reason"])

    def test_uol_host_placeholder(self):
        html = """
        <html><head><title>Página padrão UOL Host</title></head>
        <body><p>Domínio registrado no UOL Host aguardando site.</p></body></html>
        """
        result = detect_parked_or_abandoned_site(html)
        self.assertTrue(result["is_parked_or_abandoned"])
        self.assertEqual(result["category"], CATEGORY_PARKED_DOMAIN)
        self.assertIn("UOL Host", result["reason"])

    def test_namecheap_parked_page(self):
        html = """
        <html><head><title>Parked by Namecheap</title></head>
        <body><p>This domain was registered with Namecheap.</p></body></html>
        """
        result = detect_parked_or_abandoned_site(html)
        self.assertTrue(result["is_parked_or_abandoned"])
        self.assertEqual(result["category"], CATEGORY_PARKED_DOMAIN)
        self.assertIn("Namecheap", result["reason"])

    def test_sedo_parking_page(self):
        html = """
        <!DOCTYPE html>
        <html><head><title>empresa.com.br</title></head>
        <body>
            <h1>sedoparking.com</h1>
            <p>This page is provided by Sedo. Buy this domain now!</p>
        </body></html>
        """
        result = detect_parked_or_abandoned_site(html)
        self.assertTrue(result["is_parked_or_abandoned"])
        self.assertEqual(result["category"], CATEGORY_PARKED_DOMAIN)
        self.assertIn("Sedo", result["reason"])

    def test_dan_com_parking_page(self):
        html = """
        <!DOCTYPE html>
        <html><head><title>dan.com</title></head>
        <body>
            <h1>dan.com</h1>
            <p>This domain is available on dan.com for purchase.</p>
        </body></html>
        """
        result = detect_parked_or_abandoned_site(html)
        self.assertTrue(result["is_parked_or_abandoned"])
        self.assertEqual(result["category"], CATEGORY_PARKED_DOMAIN)
        self.assertIn("Dan.com", result["reason"])

    def test_generic_domain_for_sale(self):
        html = """
        <!DOCTYPE html>
        <html><head><title>meudominio.com.br</title></head>
        <body>
            <h1>Este domínio está à venda</h1>
            <p>Entre em contato para negociar a compra deste domínio corporativo.</p>
        </body></html>
        """
        result = detect_parked_or_abandoned_site(html)
        self.assertTrue(result["is_parked_or_abandoned"])
        self.assertEqual(result["category"], CATEGORY_PARKED_DOMAIN)
        self.assertIn("Venda", result["reason"])


class TestServerDefaultDetection(unittest.TestCase):
    """Tests for default web server installation pages."""

    def test_nginx_default_page(self):
        html = """
        <!DOCTYPE html>
        <html>
        <head><title>Welcome to nginx!</title></head>
        <body>
            <h1>Welcome to nginx!</h1>
            <p>If you see this page, the nginx web server is successfully installed and working. Further configuration is required.</p>
            <p><em>Thank you for using nginx.</em></p>
        </body>
        </html>
        """
        result = detect_parked_or_abandoned_site(html)
        self.assertTrue(result["is_parked_or_abandoned"])
        self.assertEqual(result["category"], CATEGORY_SERVER_DEFAULT)
        self.assertIn("Nginx", result["reason"])

    def test_apache_ubuntu_default_page(self):
        html = """
        <!DOCTYPE html>
        <html>
        <head><title>Apache2 Ubuntu Default Page: It works</title></head>
        <body>
            <h1>Apache2 Ubuntu Default Page</h1>
            <p>This is the default welcome page used to test the correct operation of the Apache2 server after installation on Ubuntu systems.</p>
        </body>
        </html>
        """
        result = detect_parked_or_abandoned_site(html)
        self.assertTrue(result["is_parked_or_abandoned"])
        self.assertEqual(result["category"], CATEGORY_SERVER_DEFAULT)
        self.assertIn("Apache", result["reason"])

    def test_apache_it_works_short_page(self):
        html = "<html><body><h1>It works!</h1></body></html>"
        result = detect_parked_or_abandoned_site(html)
        self.assertTrue(result["is_parked_or_abandoned"])
        self.assertEqual(result["category"], CATEGORY_SERVER_DEFAULT)
        self.assertIn("Apache", result["reason"])

    def test_cpanel_default_page(self):
        html = """
        <!DOCTYPE html>
        <html>
        <head><title>cPanel Default Page</title></head>
        <body>
            <h1>Great! A new cPanel &amp; WHM server has been successfully set up</h1>
            <p>This is the default placeholder page for newly created accounts on cPanel.</p>
        </body>
        </html>
        """
        result = detect_parked_or_abandoned_site(html)
        self.assertTrue(result["is_parked_or_abandoned"])
        self.assertEqual(result["category"], CATEGORY_SERVER_DEFAULT)
        self.assertIn("cPanel", result["reason"])

    def test_cpanel_url_redirect(self):
        result = detect_parked_or_abandoned_site("<html><body>Placeholder</body></html>", url="http://site.com/cgi-sys/defaultwebpage.cgi")
        self.assertTrue(result["is_parked_or_abandoned"])
        self.assertEqual(result["category"], CATEGORY_SERVER_DEFAULT)
        self.assertIn("cPanel", result["reason"])

    def test_iis_windows_server_page(self):
        html = """
        <!DOCTYPE html>
        <html>
        <head><title>IIS Windows Server</title></head>
        <body>
            <h1>Internet Information Services</h1>
            <p>Detailed documentation available on iis.net.</p>
        </body>
        </html>
        """
        result = detect_parked_or_abandoned_site(html)
        self.assertTrue(result["is_parked_or_abandoned"])
        self.assertEqual(result["category"], CATEGORY_SERVER_DEFAULT)
        self.assertIn("IIS", result["reason"])

    def test_litespeed_web_server_page(self):
        html = """
        <html><body>
            <h1>LiteSpeed Web Server</h1>
            <p>Proudly powered by LiteSpeed Web Server. Setup completed.</p>
        </body></html>
        """
        result = detect_parked_or_abandoned_site(html)
        self.assertTrue(result["is_parked_or_abandoned"])
        self.assertEqual(result["category"], CATEGORY_SERVER_DEFAULT)
        self.assertIn("LiteSpeed", result["reason"])

    def test_directory_index_listing(self):
        html = """
        <!DOCTYPE html>
        <html>
        <head><title>Index of /</title></head>
        <body>
            <h1>Index of /</h1>
            <ul>
                <li><a href="wp-content/">wp-content/</a></li>
                <li><a href="backup.sql">backup.sql</a></li>
            </ul>
        </body>
        </html>
        """
        result = detect_parked_or_abandoned_site(html)
        self.assertTrue(result["is_parked_or_abandoned"])
        self.assertEqual(result["category"], CATEGORY_SERVER_DEFAULT)
        self.assertIn("Index of /", result["reason"])


class TestCMSDefaultDetection(unittest.TestCase):
    """Tests for default CMS installations (WordPress, Joomla, Drupal)."""

    def test_wordpress_default_tagline_en(self):
        html = """
        <!DOCTYPE html>
        <html>
        <head><title>Oficina Silva – Just another WordPress site</title></head>
        <body>
            <h1>Oficina Silva</h1>
            <p>Just another WordPress site.</p>
        </body>
        </html>
        """
        result = detect_parked_or_abandoned_site(html)
        self.assertTrue(result["is_parked_or_abandoned"])
        self.assertEqual(result["category"], CATEGORY_CMS_DEFAULT)
        self.assertIn("WordPress", result["reason"])

    def test_wordpress_default_tagline_pt(self):
        html = """
        <!DOCTYPE html>
        <html>
        <head><title>Padaria São Jorge – Só mais um site WordPress</title></head>
        <body>
            <h1>Padaria São Jorge</h1>
            <p>Só mais um site WordPress.</p>
        </body>
        </html>
        """
        result = detect_parked_or_abandoned_site(html)
        self.assertTrue(result["is_parked_or_abandoned"])
        self.assertEqual(result["category"], CATEGORY_CMS_DEFAULT)
        self.assertIn("WordPress", result["reason"])

    def test_wordpress_hello_world_post_en(self):
        html = """
        <!DOCTYPE html>
        <html>
        <head><title>Minha Empresa</title></head>
        <body>
            <h2>Hello world! Welcome to WordPress</h2>
            <p>Welcome to WordPress. This is your first post. Edit or delete it, then start writing!</p>
        </body>
        </html>
        """
        result = detect_parked_or_abandoned_site(html)
        self.assertTrue(result["is_parked_or_abandoned"])
        self.assertEqual(result["category"], CATEGORY_CMS_DEFAULT)
        self.assertIn("WordPress", result["reason"])

    def test_wordpress_hello_world_post_pt(self):
        html = """
        <!DOCTYPE html>
        <html>
        <head><title>Consultoria Alpha</title></head>
        <body>
            <h2>Olá, mundo! Bem-vindo ao WordPress</h2>
            <p>Bem-vindo ao WordPress. Este é o seu primeiro post. Edite-o ou exclua-o, e comece a escrever!</p>
        </body>
        </html>
        """
        result = detect_parked_or_abandoned_site(html)
        self.assertTrue(result["is_parked_or_abandoned"])
        self.assertEqual(result["category"], CATEGORY_CMS_DEFAULT)
        self.assertIn("WordPress", result["reason"])

    def test_joomla_default_page(self):
        html = """
        <html><body>
            <h1>Welcome to your new Joomla site!</h1>
            <p>Joomla! is Free Software released under the GNU General Public License.</p>
        </body></html>
        """
        result = detect_parked_or_abandoned_site(html)
        self.assertTrue(result["is_parked_or_abandoned"])
        self.assertEqual(result["category"], CATEGORY_CMS_DEFAULT)
        self.assertIn("Joomla", result["reason"])

    def test_drupal_default_page(self):
        html = """
        <html><body>
            <h1>Welcome to your new Drupal website!</h1>
            <p>No front page content has been created yet.</p>
        </body></html>
        """
        result = detect_parked_or_abandoned_site(html)
        self.assertTrue(result["is_parked_or_abandoned"])
        self.assertEqual(result["category"], CATEGORY_CMS_DEFAULT)
        self.assertIn("Drupal", result["reason"])


class TestSuspendedAndExpiredDetection(unittest.TestCase):
    """Tests for suspended hosting accounts and expired domains."""

    def test_suspended_account_en(self):
        html = """
        <!DOCTYPE html>
        <html><head><title>Account Suspended</title></head>
        <body>
            <h1>This Account has been suspended.</h1>
            <p>Contact your hosting provider for more information.</p>
        </body></html>
        """
        result = detect_parked_or_abandoned_site(html)
        self.assertTrue(result["is_parked_or_abandoned"])
        self.assertEqual(result["category"], CATEGORY_SUSPENDED)
        self.assertIn("Suspensa", result["reason"])

    def test_suspended_account_pt(self):
        html = """
        <!DOCTYPE html>
        <html><head><title>Aviso</title></head>
        <body>
            <h1>Esta conta foi suspensa</h1>
            <p>Sua conta de hospedagem foi suspensa. Entre em contato com o suporte financeiro.</p>
        </body></html>
        """
        result = detect_parked_or_abandoned_site(html)
        self.assertTrue(result["is_parked_or_abandoned"])
        self.assertEqual(result["category"], CATEGORY_SUSPENDED)
        self.assertIn("Suspensa", result["reason"])

    def test_domain_expired_en(self):
        html = """
        <html><head><title>Domain Expired</title></head>
        <body>
            <h1>This domain has expired</h1>
            <p>Renew your domain before it is permanently deleted.</p>
        </body></html>
        """
        result = detect_parked_or_abandoned_site(html)
        self.assertTrue(result["is_parked_or_abandoned"])
        self.assertEqual(result["category"], CATEGORY_SUSPENDED)
        self.assertIn("Expirado", result["reason"])

    def test_domain_expired_pt(self):
        html = """
        <html><head><title>Aviso de Domínio</title></head>
        <body>
            <h1>Domínio Expirado</h1>
            <p>O domínio expirou e está temporariamente congelado aguardando renovação.</p>
        </body></html>
        """
        result = detect_parked_or_abandoned_site(html)
        self.assertTrue(result["is_parked_or_abandoned"])
        self.assertEqual(result["category"], CATEGORY_SUSPENDED)
        self.assertIn("Expirado", result["reason"])

    def test_bandwidth_limit_exceeded(self):
        html = "<html><body><h1>Bandwidth Limit Exceeded</h1><p>The server cannot serve more traffic.</p></body></html>"
        result = detect_parked_or_abandoned_site(html)
        self.assertTrue(result["is_parked_or_abandoned"])
        self.assertEqual(result["category"], CATEGORY_SUSPENDED)


class TestUnderConstructionDetection(unittest.TestCase):
    """Tests for under construction and maintenance placeholders."""

    def test_under_construction_title_pt(self):
        html = """
        <!DOCTYPE html>
        <html><head><title>Site em Construção</title></head>
        <body><p>Em breve novidades para você.</p></body></html>
        """
        result = detect_parked_or_abandoned_site(html)
        self.assertTrue(result["is_parked_or_abandoned"])
        self.assertEqual(result["category"], CATEGORY_UNDER_CONSTRUCTION)
        self.assertIn("Construção", result["reason"])

    def test_under_construction_heading_pt(self):
        html = """
        <!DOCTYPE html>
        <html><head><title>Minha Empresa</title></head>
        <body>
            <h1>Página em Construção</h1>
            <p>Estamos trabalhando no desenvolvimento do novo portal da empresa. Aguarde!</p>
        </body></html>
        """
        result = detect_parked_or_abandoned_site(html)
        self.assertTrue(result["is_parked_or_abandoned"])
        self.assertEqual(result["category"], CATEGORY_UNDER_CONSTRUCTION)
        self.assertIn("Construção", result["reason"])

    def test_under_construction_body_text_pt(self):
        html = """
        <!DOCTYPE html>
        <html><head><title>Bem-vindo</title></head>
        <body>
            <h2>Aguarde</h2>
            <p>Nosso site está em construção. Em breve um novo site no ar!</p>
        </body></html>
        """
        result = detect_parked_or_abandoned_site(html)
        self.assertTrue(result["is_parked_or_abandoned"])
        self.assertEqual(result["category"], CATEGORY_UNDER_CONSTRUCTION)

    def test_site_in_maintenance(self):
        html = """
        <!DOCTYPE html>
        <html><head><title>Site em Manutenção</title></head>
        <body>
            <h1>Desculpe o transtorno, estamos em manutenção</h1>
            <p>Voltaremos em breve com uma experiência aprimorada.</p>
        </body></html>
        """
        result = detect_parked_or_abandoned_site(html)
        self.assertTrue(result["is_parked_or_abandoned"])
        self.assertEqual(result["category"], CATEGORY_UNDER_CONSTRUCTION)
        self.assertIn("Manutenção", result["reason"])

    def test_coming_soon_en(self):
        html = """
        <!DOCTYPE html>
        <html><head><title>Coming Soon</title></head>
        <body>
            <h1>Coming Soon</h1>
            <p>Our website is currently under construction. Stay tuned for exciting updates!</p>
        </body></html>
        """
        result = detect_parked_or_abandoned_site(html)
        self.assertTrue(result["is_parked_or_abandoned"])
        self.assertEqual(result["category"], CATEGORY_UNDER_CONSTRUCTION)


class TestFalsePositiveProtection(unittest.TestCase):
    """
    CRITICAL TESTS: Ensures legitimate businesses that use terms like
    'construção civil', 'manutenção de carros', or 'manutenção preventiva'
    are NEVER falsely flagged as under construction or abandoned.
    """

    def test_civil_construction_company_is_legitimate(self):
        html = """
        <!DOCTYPE html>
        <html lang="pt-BR">
        <head>
            <title>Construtora Andrade - Obras e Construção Civil em São Paulo</title>
        </head>
        <body>
            <header>
                <nav><a href="#sobre">Sobre Nós</a> | <a href="#servicos">Serviços</a> | <a href="#contato">Contato</a></nav>
            </header>
            <h1>Construção Civil e Reformas Prediais de Alto Padrão</h1>
            <p>Somos uma empresa de construção civil consolidada com mais de 20 anos de tradição. Realizamos construção residencial, construção comercial e grandes empreendimentos em toda a capital.</p>
            <h2>Nossos Serviços de Construção</h2>
            <ul>
                <li>Construção e reforma de galpões industriais</li>
                <li>Gerenciamento completo de obras e engenharia</li>
                <li>Materiais de construção de procedência certificada ABNT</li>
            </ul>
            <p>Atendemos clientes residenciais e corporativos com excelência, segurança e pontualidade na entrega de cada etapa do projeto.</p>
            <footer>
                <p>Telefone: (11) 3456-7890 | E-mail: contato@andradeconstrucao.com.br</p>
                <p>Endereço: Av. das Nações Unidas, 12000 - São Paulo, SP</p>
            </footer>
        </body>
        </html>
        """
        result = detect_parked_or_abandoned_site(html)
        self.assertFalse(result["is_parked_or_abandoned"])
        self.assertEqual(result["category"], CATEGORY_NONE)
        self.assertEqual(result["reason"], "")
        self.assertEqual(result["confidence"], 0.0)

    def test_auto_mechanic_maintenance_is_legitimate(self):
        html = """
        <!DOCTYPE html>
        <html lang="pt-BR">
        <head>
            <title>Auto Mecânica Paulista - Especialistas em Manutenção de Carros</title>
        </head>
        <body>
            <header>
                <h1>Oficina Mecânica Especializada</h1>
            </header>
            <p>Oferecemos serviços completos de reparação automotiva e manutenção de carros nacionais e importados com tecnologia de ponta.</p>
            <h2>Serviços Automotivos</h2>
            <ul>
                <li>Manutenção preventiva de motores e injeção eletrônica</li>
                <li>Manutenção corretiva de freios, embreagem e suspensão</li>
                <li>Troca de óleo, filtros e revisão completa de 10.000 km</li>
            </ul>
            <p>Confie a manutenção automotiva do seu veículo a mecânicos certificados com equipamentos de diagnóstico computadorizado de última geração.</p>
            <footer>
                <p>Agende sua revisão pelo WhatsApp: (11) 98765-4321</p>
                <p>Rua Augusta, 450 - Consolação - São Paulo, SP</p>
            </footer>
        </body>
        </html>
        """
        result = detect_parked_or_abandoned_site(html)
        self.assertFalse(result["is_parked_or_abandoned"])
        self.assertEqual(result["category"], CATEGORY_NONE)
        self.assertEqual(result["reason"], "")
        self.assertEqual(result["confidence"], 0.0)

    def test_hvac_maintenance_company_is_legitimate(self):
        html = """
        <!DOCTYPE html>
        <html lang="pt-BR">
        <head>
            <title>ClimaTech - Instalação e Manutenção de Ar Condicionado</title>
        </head>
        <body>
            <h1>Manutenção de Ar Condicionado Residencial e Comercial</h1>
            <p>A ClimaTech oferece contratos de manutenção preventiva e limpeza periódica de sistemas de climatização, cumprindo todas as normas da ANVISA (PMOC).</p>
            <h2>Diferenciais dos Nossos Serviços</h2>
            <p>Nossos técnicos especializados realizam higienização química, troca de filtros e manutenção corretiva rápida para empresas e hospitais.</p>
            <footer>
                <p>Telefone: (19) 3211-9988 | Atendemos Campinas e Região</p>
            </footer>
        </body>
        </html>
        """
        result = detect_parked_or_abandoned_site(html)
        self.assertFalse(result["is_parked_or_abandoned"])
        self.assertEqual(result["category"], CATEGORY_NONE)
        self.assertEqual(result["reason"], "")

    def test_it_computer_maintenance_is_legitimate(self):
        html = """
        <!DOCTYPE html>
        <html lang="pt-BR">
        <head>
            <title>InfoFix - Manutenção de Computadores e Redes</title>
        </head>
        <body>
            <h1>Manutenção de Computadores e Notebooks</h1>
            <p>Assistência técnica especializada em manutenção preventiva, troca de componentes, montagem de computadores gamer e suporte a servidores corporativos.</p>
            <p>Visite nossa loja na Rua Santa Ifigênia ou solicite orçamento online.</p>
            <footer>Telefone: (11) 3322-1100</footer>
        </body>
        </html>
        """
        result = detect_parked_or_abandoned_site(html)
        self.assertFalse(result["is_parked_or_abandoned"])
        self.assertEqual(result["category"], CATEGORY_NONE)
        self.assertEqual(result["reason"], "")

    def test_dental_clinic_full_website_is_legitimate(self):
        html = """
        <!DOCTYPE html>
        <html>
        <head><title>Clínica Odontológica Dr. Silva - Implantes e Ortodontia</title></head>
        <body>
            <h1>Sorriso Perfeito com Quem Entende de Odontologia</h1>
            <p>Atendemos você e sua família com os melhores tratamentos odontológicos modernos: clareamento dental a laser, alinhadores transparentes e próteses fixas.</p>
            <p>Agende sua consulta com nossa equipe de cirurgiões dentistas.</p>
            <footer>Contato: (21) 2233-4455 - Copacabana, Rio de Janeiro</footer>
        </body>
        </html>
        """
        result = detect_parked_or_abandoned_site(html)
        self.assertFalse(result["is_parked_or_abandoned"])
        self.assertEqual(result["category"], CATEGORY_NONE)
        self.assertEqual(result["confidence"], 0.0)


class TestBlankAndShortPages(unittest.TestCase):
    """Tests for empty, nearly empty, and minimal content pages."""

    def test_completely_empty_string(self):
        result = detect_parked_or_abandoned_site("")
        self.assertTrue(result["is_parked_or_abandoned"])
        self.assertEqual(result["category"], CATEGORY_BLANK_PAGE)
        self.assertEqual(result["confidence"], 1.0)
        self.assertIn("Página em Branco", result["reason"])

    def test_none_input(self):
        result = detect_parked_or_abandoned_site(None)
        self.assertTrue(result["is_parked_or_abandoned"])
        self.assertEqual(result["category"], CATEGORY_BLANK_PAGE)
        self.assertEqual(result["confidence"], 1.0)

    def test_whitespace_and_empty_tags_only(self):
        html = "<html><head><title></title></head><body>   \n\t   </body></html>"
        result = detect_parked_or_abandoned_site(html)
        self.assertTrue(result["is_parked_or_abandoned"])
        self.assertEqual(result["category"], CATEGORY_BLANK_PAGE)
        self.assertEqual(result["confidence"], 1.0)

    def test_only_html_comments(self):
        html = "<html><!-- This is a commented site with no visible body --></html>"
        result = detect_parked_or_abandoned_site(html)
        self.assertTrue(result["is_parked_or_abandoned"])
        self.assertEqual(result["category"], CATEGORY_BLANK_PAGE)
        self.assertEqual(result["confidence"], 1.0)

    def test_nearly_blank_short_page_under_80_chars(self):
        # 30 chars of random uninformative content
        html = "<html><body><div>OK teste temporário</div></body></html>"
        result = detect_parked_or_abandoned_site(html)
        self.assertTrue(result["is_parked_or_abandoned"])
        self.assertEqual(result["category"], CATEGORY_BLANK_PAGE)
        self.assertIn("Quase Vazia", result["reason"])
        self.assertEqual(result["confidence"], 0.85)


class TestEdgeCasesAndInputs(unittest.TestCase):
    """Tests for edge cases, non-string types, and return contract consistency."""

    def test_bytes_input(self):
        raw_bytes = b"<html><head><title>Welcome to nginx!</title></head><body><h1>Welcome to nginx!</h1></body></html>"
        result = detect_parked_or_abandoned_site(raw_bytes)
        self.assertTrue(result["is_parked_or_abandoned"])
        self.assertEqual(result["category"], CATEGORY_SERVER_DEFAULT)

    def test_return_contract_has_all_required_keys(self):
        cases = [
            "",
            "<html><body><h1>Welcome to nginx!</h1></body></html>",
            "<html><head><title>Site em Construção</title></head><body><p>Em breve</p></body></html>",
            "<html><body><h1>Oficina Mecânica</h1><p>Manutenção de carros preventiva com atendimento de qualidade.</p></body></html>",
        ]
        required_keys = {"is_parked_or_abandoned", "category", "reason", "confidence"}
        for html in cases:
            res = detect_parked_or_abandoned_site(html)
            self.assertTrue(required_keys.issubset(res.keys()))
            self.assertIsInstance(res["is_parked_or_abandoned"], bool)
            self.assertIsInstance(res["category"], str)
            self.assertIsInstance(res["reason"], str)
            self.assertIsInstance(res["confidence"], float)
            self.assertGreaterEqual(res["confidence"], 0.0)
            self.assertLessEqual(res["confidence"], 1.0)


if __name__ == "__main__":
    unittest.main()
