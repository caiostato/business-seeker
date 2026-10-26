"""
test_enrichment.py - Comprehensive Unit Tests for Lead Enrichment & Site Health
"""

import unittest
from unittest.mock import MagicMock, patch
import requests

from enrichment import (
    classify_web_presence,
    parse_brazilian_phone,
    classify_phone_type,
    generate_whatsapp_url,
    extract_contact_info,
    check_website_health,
    calculate_lead_score,
    fetch_page_sample,
    enrich_single_lead,
    enrich_leads_parallel,
)


class TestClassifyWebPresence(unittest.TestCase):
    """Tests for Brazilian Web Presence Classifier."""

    def test_none_or_empty_url(self):
        for empty_val in [None, "", "   ", "Nenhum", "n/a", "N/A", "-", "null"]:
            result = classify_web_presence(empty_val)
            self.assertEqual(result["kind"], "NONE")
            self.assertEqual(result["label"], "🚫 Sem Site")
            self.assertFalse(result["is_custom"])
            self.assertTrue(result["is_lead_candidate"])

    def test_whatsapp_domains(self):
        wa_urls = [
            "https://wa.me/5511999999999",
            "http://api.whatsapp.com/send?phone=5511999999999",
            "https://chat.whatsapp.com/InviteCode123",
            "https://whats.link/minhaempresa",
            "https://whatsapp.com/channel/0029Va",
            "wa.me/5511988887777",
        ]
        for url in wa_urls:
            result = classify_web_presence(url)
            self.assertEqual(result["kind"], "WHATSAPP", f"Failed for {url}")
            self.assertEqual(result["label"], "💬 WhatsApp Link")
            self.assertFalse(result["is_custom"])
            self.assertTrue(result["is_lead_candidate"])

    def test_social_media_domains(self):
        social_urls = [
            "https://www.instagram.com/marcenaria_silva",
            "http://facebook.com/minhaempresa",
            "https://fb.com/oficina",
            "https://tiktok.com/@estetica_sp",
            "https://twitter.com/loja",
            "https://x.com/oficina",
            "https://linkedin.com/company/consultoria",
            "https://youtube.com/@canal",
            "instagram.com/dentista",
        ]
        for url in social_urls:
            result = classify_web_presence(url)
            self.assertEqual(result["kind"], "SOCIAL", f"Failed for {url}")
            self.assertEqual(result["label"], "📱 Rede Social")
            self.assertFalse(result["is_custom"])

    def test_linktree_and_free_builders(self):
        free_builder_urls = [
            "https://linktr.ee/minhaoficina",
            "https://bio.site/consultorio",
            "https://beacons.ai/perfil",
            "https://carrd.co/build",
            "https://clinica.carrd.co",
            "https://empresa.canva.site",
            "https://sites.google.com/view/barbearia",
            "https://oficina.wixsite.com/site",
            "https://loja.wordpress.com",
            "https://blog.blogspot.com",
            "https://barbearia.meu.negocio",
            "https://bento.me/user",
            "https://taplink.cc/user",
            "https://solo.to/user",
            "https://bit.ly/meu-link",
            "https://linklist.bio/empresa",
            "https://minhaempresa.weebly.com",
        ]
        for url in free_builder_urls:
            result = classify_web_presence(url)
            self.assertEqual(result["kind"], "LINKTREE_FREE", f"Failed for {url}")
            self.assertEqual(result["label"], "🔗 Link na Bio / Construtor Grátis")
            self.assertFalse(result["is_custom"])

    def test_directories_and_delivery(self):
        directory_urls = [
            "https://ifood.com.br/delivery/sp/restaurante",
            "https://www.ifood.com.br/restaurante/123",
            "https://guiamais.com.br/empresa",
            "https://solutudo.com.br/empresas/sp/campinas/oficina",
            "https://doctoralia.com.br/medico",
            "https://telelistas.net/empresa",
            "https://apontador.com.br/local",
            "https://kekanto.com.br/biz/restaurante",
        ]
        for url in directory_urls:
            result = classify_web_presence(url)
            self.assertEqual(result["kind"], "DIRECTORY", f"Failed for {url}")
            self.assertEqual(result["label"], "📂 Guia / Plataforma Externa")
            self.assertFalse(result["is_custom"])

    def test_custom_domains(self):
        custom_urls = [
            "https://oficinadosilva.com.br",
            "http://marmorariasp.net.br",
            "https://consultorio-odonto.med.br",
            "https://serralheriapro.com",
            "marcenariasp.com.br",
        ]
        for url in custom_urls:
            result = classify_web_presence(url)
            self.assertEqual(result["kind"], "CUSTOM_DOMAIN", f"Failed for {url}")
            self.assertEqual(result["label"], "🌐 Domínio Próprio")
            self.assertTrue(result["is_custom"])
            self.assertFalse(result["is_lead_candidate"])


class TestBrazilianPhoneFormatter(unittest.TestCase):
    """Tests for Brazilian Phone Formatter & Type Classifier."""

    def test_mobile_whatsapp_phones(self):
        cases = [
            ("(11) 98765-4321", "5511987654321", "(11) 98765-4321"),
            ("+55 11 98765-4321", "5511987654321", "(11) 98765-4321"),
            ("11987654321", "5511987654321", "(11) 98765-4321"),
            ("011987654321", "5511987654321", "(11) 98765-4321"),
            ("+55 (21) 99887-7665", "5521998877665", "(21) 99887-7665"),
            ("(85) 98888-7777", "5585988887777", "(85) 98888-7777"),
        ]
        for input_phone, expected_e164, expected_formatted in cases:
            res = parse_brazilian_phone(input_phone)
            self.assertTrue(res["is_valid"], f"Should be valid: {input_phone}")
            self.assertTrue(res["is_mobile"], f"Should be mobile: {input_phone}")
            self.assertEqual(res["type"], "📱 Celular / WhatsApp")
            self.assertEqual(res["e164"], expected_e164)
            self.assertEqual(res["formatted"], expected_formatted)
            self.assertEqual(classify_phone_type(input_phone), "📱 Celular / WhatsApp")

    def test_landline_fixo_phones(self):
        cases = [
            ("(11) 3344-5566", "551133445566", "(11) 3344-5566"),
            ("+55 11 2345-6789", "551123456789", "(11) 2345-6789"),
            ("(21) 4567-8901", "552145678901", "(21) 4567-8901"),
            ("03133221100", "553133221100", "(31) 3322-1100"),
            ("(41) 5678-9012", "554156789012", "(41) 5678-9012"),
        ]
        for input_phone, expected_e164, expected_formatted in cases:
            res = parse_brazilian_phone(input_phone)
            self.assertTrue(res["is_valid"], f"Should be valid: {input_phone}")
            self.assertFalse(res["is_mobile"], f"Should not be mobile: {input_phone}")
            self.assertEqual(res["type"], "☎️ Fixo")
            self.assertEqual(res["e164"], expected_e164)
            self.assertEqual(res["formatted"], expected_formatted)
            self.assertEqual(classify_phone_type(input_phone), "☎️ Fixo")

    def test_invalid_phones(self):
        invalid_cases = [
            "",
            None,
            "12345",
            "0000000000",
            "+55 (00) 98765-4321",  # Invalid DDD 00
            "+55 (11) 1234-5678",   # Landline cannot start with 1
            "+55 (11) 88765-4321",  # Mobile must start with 9
            "telefone",
        ]
        for inv in invalid_cases:
            res = parse_brazilian_phone(inv)
            self.assertFalse(res["is_valid"], f"Should be invalid: {inv}")
            self.assertEqual(res["type"], "Invalido")
            self.assertEqual(res["e164"], "")
            self.assertEqual(classify_phone_type(inv), "Invalido")


class TestWhatsAppUrlGenerator(unittest.TestCase):
    """Tests for WhatsApp 1-Click Link Generator."""

    def test_valid_link_default_template(self):
        url = generate_whatsapp_url(
            phone="(11) 98765-4321",
            business_name="Oficina Silva",
            niche="Oficina Mecânica",
        )
        self.assertTrue(url.startswith("https://wa.me/5511987654321?text="))
        self.assertIn("Oficina%20Silva", url)
        self.assertIn("Oficina%20Mec%C3%A2nica", url)

    def test_valid_link_custom_template(self):
        custom = "Fala time da {business_name}! Temos novidades para {niche}."
        url = generate_whatsapp_url(
            phone="+55 11 98765-4321",
            business_name="Marmoraria Central",
            niche="Marmoraria",
            custom_template=custom,
        )
        self.assertTrue(url.startswith("https://wa.me/5511987654321?text="))
        self.assertIn("Fala%20time%20da%20Marmoraria%20Central", url)

    def test_fallback_placeholders(self):
        url = generate_whatsapp_url(
            phone="(11) 98765-4321",
            business_name="",
            niche="",
        )
        self.assertTrue(url.startswith("https://wa.me/5511987654321?text="))
        self.assertIn("sua%20empresa", url)
        self.assertIn("seus%20servi%C3%A7os", url)

    def test_invalid_phone_returns_empty(self):
        self.assertEqual(generate_whatsapp_url("12345", "Empresa", "Nicho"), "")
        self.assertEqual(generate_whatsapp_url("", "Empresa", "Nicho"), "")
        self.assertEqual(generate_whatsapp_url(None, "Empresa", "Nicho"), "")


class TestContactExtraction(unittest.TestCase):
    """Tests for contact information extraction from HTML."""

    def test_extract_emails_and_filter_junk(self):
        html = """
        <html>
            <body>
                <a href="mailto:contato@oficinadosilva.com.br">Fale Conosco</a>
                <a href="mailto:test@example.com">Exemplo</a>
                <p>Nosso suporte: suporte@oficinadosilva.com.br</p>
                <script>const sentry = "err@sentry.io";</script>
                <img src="icon@2x.png" />
            </body>
        </html>
        """
        extracted = extract_contact_info(html)
        self.assertIn("contato@oficinadosilva.com.br", extracted["emails"])
        self.assertIn("suporte@oficinadosilva.com.br", extracted["emails"])
        self.assertEqual(extracted["primary_email"], "contato@oficinadosilva.com.br")

        # Junk filtered
        self.assertNotIn("test@example.com", extracted["emails"])
        self.assertNotIn("err@sentry.io", extracted["emails"])
        for e in extracted["emails"]:
            self.assertFalse(e.endswith(".png"))

    def test_extract_instagram_and_filter_junk(self):
        html = """
        <div>
            <a href="https://instagram.com/explore/">Explore</a>
            <a href="https://instagram.com/p/C7Xabc123/">Post</a>
            <a href="https://www.instagram.com/marcenariaplanejada/">Nosso Insta</a>
        </div>
        """
        extracted = extract_contact_info(html)
        self.assertIsNotNone(extracted["instagram"])
        self.assertEqual(extracted["instagram"]["handle"], "@marcenariaplanejada")
        self.assertEqual(extracted["instagram"]["url"], "https://instagram.com/marcenariaplanejada")

    def test_extract_facebook_and_whatsapp(self):
        html = """
        <div>
            <a href="https://www.facebook.com/sharer/sharer.php?u=foo">Share</a>
            <a href="https://facebook.com/oficinaprime">Facebook</a>
            <a href="https://wa.me/5511999998888">WhatsApp</a>
        </div>
        """
        extracted = extract_contact_info(html)
        self.assertEqual(extracted["facebook"], "https://facebook.com/oficinaprime")
        self.assertIn("https://wa.me/5511999998888", extracted["whatsapp_links"])
        self.assertIn("5511999998888", extracted["whatsapp_phones"])


class TestWebsiteHealthCheck(unittest.TestCase):
    """Tests for Website Health Checker with mocked network requests."""

    def test_empty_url(self):
        res = check_website_health("")
        self.assertEqual(res["status"], "🚫 Sem Site")
        self.assertFalse(res["is_healthy"])

        res2 = check_website_health("Nenhum")
        self.assertEqual(res2["status"], "🚫 Sem Site")

    @patch("requests.Session")
    def test_healthy_https_website(self, mock_session_cls):
        mock_session = MagicMock()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.url = "https://oficinadosilva.com.br"
        mock_session.head.return_value = mock_resp
        mock_session_cls.return_value = mock_session

        res = check_website_health("https://oficinadosilva.com.br")
        self.assertEqual(res["status"], "✅ Site Operacional")
        self.assertTrue(res["is_healthy"])
        self.assertTrue(res["has_https"])
        self.assertEqual(res["status_code"], 200)

    @patch("requests.Session")
    def test_ssl_error(self, mock_session_cls):
        mock_session = MagicMock()
        mock_session.head.side_effect = requests.exceptions.SSLError("Certificate invalid")
        mock_session.get.side_effect = requests.exceptions.SSLError("Certificate invalid")
        mock_session_cls.return_value = mock_session

        res = check_website_health("https://expired-ssl.com.br")
        self.assertEqual(res["status"], "🔓 Sem HTTPS (Inseguro)")
        self.assertFalse(res["is_healthy"])
        self.assertFalse(res["has_https"])
        self.assertIn("SSL", res["error"])

    @patch("requests.Session")
    def test_http_only_insecure(self, mock_session_cls):
        mock_session = MagicMock()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.url = "http://insecure-site.com.br"
        mock_session.head.return_value = mock_resp
        mock_session_cls.return_value = mock_session

        res = check_website_health("http://insecure-site.com.br")
        self.assertEqual(res["status"], "🔓 Sem HTTPS (Inseguro)")
        self.assertFalse(res["is_healthy"])
        self.assertFalse(res["has_https"])

    @patch("requests.Session")
    def test_site_offline_connection_error(self, mock_session_cls):
        mock_session = MagicMock()
        mock_session.head.side_effect = requests.exceptions.ConnectionError("DNS failure")
        mock_session.get.side_effect = requests.exceptions.ConnectionError("DNS failure")
        mock_session_cls.return_value = mock_session

        res = check_website_health("https://nonexistent-domain-xyz123.com")
        self.assertEqual(res["status"], "⚠️ Site Fora do Ar")
        self.assertFalse(res["is_healthy"])

    @patch("requests.Session")
    def test_head_405_fallback_to_get_success(self, mock_session_cls):
        mock_session = MagicMock()
        head_resp = MagicMock()
        head_resp.status_code = 405
        get_resp = MagicMock()
        get_resp.status_code = 200
        get_resp.url = "https://cloudflare-protected.com.br"

        mock_session.head.return_value = head_resp
        mock_session.get.return_value = get_resp
        mock_session_cls.return_value = mock_session

        res = check_website_health("https://cloudflare-protected.com.br")
        self.assertEqual(res["status"], "✅ Site Operacional")
        self.assertTrue(res["is_healthy"])
        self.assertEqual(res["status_code"], 200)
        mock_session.get.assert_called_once()

    @patch("enrichment.fetch_page_sample")
    @patch("requests.Session")
    def test_parked_godaddy_site_detected(self, mock_session_cls, mock_fetch):
        mock_session = MagicMock()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.url = "https://oficinaestacionada.com.br"
        mock_session.head.return_value = mock_resp
        mock_session_cls.return_value = mock_session

        mock_fetch.return_value = """
        <html><head><title>Parked Page</title></head>
        <body>
            <h1>Parked FREE, courtesy of GoDaddy.com</h1>
            <p>This Web page is parked FREE, courtesy of GoDaddy. What is this page?</p>
        </body></html>
        """

        res = check_website_health("https://oficinaestacionada.com.br")
        self.assertTrue(res["is_parked"])
        self.assertFalse(res["is_healthy"])
        self.assertIn("Domínio Estacionado", res["status"])

    @patch("enrichment.fetch_page_sample")
    @patch("requests.Session")
    def test_non_responsive_site_detected(self, mock_session_cls, mock_fetch):
        mock_session = MagicMock()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.url = "https://sitenaoresponsivo.com.br"
        mock_session.head.return_value = mock_resp
        mock_session_cls.return_value = mock_session

        # Valid site with lots of text but NO viewport tag
        mock_fetch.return_value = "<html><head><title>Oficina Antiga</title></head><body>" + ("<p>Serviços de mecânica e conserto automotivo.</p>" * 10) + "</body></html>"

        res = check_website_health("https://sitenaoresponsivo.com.br")
        self.assertTrue(res.get("is_redesign_candidate"))
        self.assertFalse(res["is_healthy"])
        self.assertEqual(res["status"], "📱 Site Não Responsivo (Redesign)")


class TestFetchPageSample(unittest.TestCase):
    """Tests for stream fetching with byte limits."""

    def test_empty_url(self):
        self.assertIsNone(from_enrichment := fetch_page_sample(""))

    @patch("requests.get")
    def test_fetch_chunks_and_stops_at_max_bytes(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.iter_content.return_value = [b"a" * 500, b"b" * 500, b"c" * 500]
        mock_get.return_value = mock_resp

        content = fetch_page_sample("https://example.com", max_bytes=800)
        self.assertIsNotNone(content)
        self.assertLessEqual(len(content), 1000)



class TestLeadScoring(unittest.TestCase):
    """Tests for Lead Scoring (0-100) and Temperature."""

    def test_hot_lead_scoring(self):
        # 60 reviews (+35), 4.8 rating (+20), mobile (+25), sem site (+10) = 90 pts
        place = {
            "displayName": {"text": "Auto Mecânica Prime"},
            "userRatingCount": 60,
            "rating": 4.8,
            "nationalPhoneNumber": "(11) 98765-4321",
            "websiteUri": None,
        }
        score = calculate_lead_score(place)
        self.assertEqual(score["score"], 90)
        self.assertEqual(score["temperature"], "🔥 Quente")
        self.assertEqual(score["breakdown"]["reviews"], 35)
        self.assertEqual(score["breakdown"]["rating"], 20)
        self.assertEqual(score["breakdown"]["contact"], 25)
        self.assertEqual(score["breakdown"]["digital_pain"], 10)
        self.assertTrue(any("Alto volume" in r for r in score["reasons"]))
        self.assertTrue(any("Excelente reputação" in r for r in score["reasons"]))

    def test_medium_lead_scoring(self):
        # 20 reviews (+25), 4.0 rating (+10), landline (+10), linktree (+10) = 55 pts
        place = {
            "Nome da Empresa": "Clínica Bem Estar",
            "Avaliação": "4.0⭐ (20)",
            "Telefone": "(11) 3344-5566",
            "Site / Rede Social": "https://linktr.ee/bemestar",
        }
        score = calculate_lead_score(place)
        self.assertEqual(score["score"], 55)
        self.assertEqual(score["temperature"], "⚡ Médio")
        self.assertEqual(score["breakdown"]["reviews"], 25)
        self.assertEqual(score["breakdown"]["rating"], 10)
        self.assertEqual(score["breakdown"]["contact"], 10)
        self.assertEqual(score["breakdown"]["digital_pain"], 10)

    def test_cold_lead_scoring(self):
        # 2 reviews (+5), 3.5 rating (+0), no phone (+0), sem site (+10) = 15 pts
        place = {
            "displayName": {"text": "Chaveiro do Bairro"},
            "userRatingCount": 2,
            "rating": 3.5,
            "nationalPhoneNumber": None,
            "websiteUri": "",
        }
        score = calculate_lead_score(place)
        self.assertEqual(score["score"], 15)
        self.assertEqual(score["temperature"], "❄️ Frio")

    def test_broken_site_pain_points(self):
        # Reviews 50 (+35), Rating 4.5 (+20), Mobile (+25), Broken site (+15) = 95 pts
        place = {
            "displayName": {"text": "Marmoraria Silva"},
            "userRatingCount": 50,
            "rating": 4.5,
            "nationalPhoneNumber": "(11) 98765-4321",
            "websiteUri": "https://marmorariasilva.com.br",
        }
        enriched_info = {
            "site_health": {"status": "⚠️ Site Fora do Ar"},
            "web_presence": {"kind": "CUSTOM_DOMAIN"},
        }
        score = calculate_lead_score(place, enriched_info)
        self.assertEqual(score["score"], 95)
        self.assertEqual(score["temperature"], "🔥 Quente")
        self.assertEqual(score["breakdown"]["digital_pain"], 15)
        self.assertTrue(any("fora do ar" in r for r in score["reasons"]))

    def test_parked_site_pain_points(self):
        # Reviews 50 (+35), Rating 4.5 (+20), Mobile (+25), Parked site (+20) = 100 pts
        place = {
            "displayName": {"text": "Oficina Moema"},
            "userRatingCount": 50,
            "rating": 4.5,
            "nationalPhoneNumber": "(11) 98765-4321",
            "websiteUri": "https://oficinamoema.com.br",
        }
        enriched_info = {
            "site_health": {"status": "⚠️ Domínio Estacionado (GoDaddy)", "is_parked": True},
            "web_presence": {"kind": "CUSTOM_DOMAIN"},
        }
        score = calculate_lead_score(place, enriched_info)
        self.assertEqual(score["score"], 100)
        self.assertEqual(score["temperature"], "🔥 Quente")
        self.assertEqual(score["breakdown"]["digital_pain"], 20)
        self.assertTrue(any("inativo" in r for r in score["reasons"]))

    def test_redesign_site_pain_points(self):
        # Reviews 50 (+35), Rating 4.5 (+20), Mobile (+25), Redesign/Not mobile friendly (+15) = 95 pts
        place = {
            "displayName": {"text": "Clínica Paulista"},
            "userRatingCount": 50,
            "rating": 4.5,
            "nationalPhoneNumber": "(11) 98765-4321",
            "websiteUri": "https://clinicapaulista.com.br",
        }
        enriched_info = {
            "site_health": {"status": "📱 Site Não Responsivo (Redesign)", "is_redesign_candidate": True},
            "web_presence": {"kind": "CUSTOM_DOMAIN"},
        }
        score = calculate_lead_score(place, enriched_info)
        self.assertEqual(score["score"], 95)
        self.assertEqual(score["temperature"], "🔥 Quente")
        self.assertEqual(score["breakdown"]["digital_pain"], 15)
        self.assertTrue(any("Redesign" in r for r in score["reasons"]))

    def test_score_temperature_boundaries(self):
        # Boundary 70 points: 5 reviews (+15), 4.5 rating (+20), mobile (+25), sem site (+10) = 70 -> Hot
        p70 = {
            "userRatingCount": 5,
            "rating": 4.5,
            "nationalPhoneNumber": "(11) 98765-4321",
            "websiteUri": "",
        }
        res70 = calculate_lead_score(p70)
        self.assertEqual(res70["score"], 70)
        self.assertEqual(res70["temperature"], "🔥 Quente")

        # Score 65: 20 reviews (+25), 4.5 rating (+20), fixo (+10), sem site (+10) = 65 -> Medium
        p65 = {
            "userRatingCount": 20,
            "rating": 4.5,
            "nationalPhoneNumber": "(11) 3344-5566",
            "websiteUri": "",
        }
        res65 = calculate_lead_score(p65)
        self.assertEqual(res65["score"], 65)
        self.assertEqual(res65["temperature"], "⚡ Médio")

        # Score 40: 15 reviews (+25), 3.5 rating (+0), fixo (+10), linktree with custom domain operational (+0, wait 15 reviews (+25) + fixo (+10) + 1 review? Let's check:
        # Reviews 1-4 (+5), rating 4.2 (+20), fixo (+10), linktree pain (+10) = 45 -> Medium
        # Reviews 1-4 (+5), rating 3.8 (+10), fixo (+10), sem site (+10), 5+10+10+10 = 35 -> Cold
        p35 = {
            "userRatingCount": 2,
            "rating": 3.9,
            "nationalPhoneNumber": "(11) 3344-5566",
            "websiteUri": "",
        }
        res35 = calculate_lead_score(p35)
        self.assertEqual(res35["score"], 35)
        self.assertEqual(res35["temperature"], "❄️ Frio")

    def test_score_capping_at_100(self):
        # 100 reviews (+35), 5.0 (+20), mobile (+25), extracted contact (+10), broken site (+15) = 105 -> capped to 100
        place = {
            "userRatingCount": 100,
            "rating": 5.0,
            "nationalPhoneNumber": "(11) 98765-4321",
            "websiteUri": "https://site.com",
        }
        enriched_info = {
            "site_health": {"status": "⚠️ Site Fora do Ar"},
            "extracted_email": "contato@site.com",
        }
        score = calculate_lead_score(place, enriched_info)
        self.assertEqual(score["score"], 100)


class TestParallelEnrichment(unittest.TestCase):
    """Tests for single lead enrichment and multi-threaded parallel batch execution."""

    @patch("enrichment.fetch_page_sample")
    def test_enrich_single_lead_bio(self, mock_fetch):
        mock_fetch.return_value = """
        <html>
            <body>
                <a href="mailto:orcamento@vidros.com.br">Email</a>
                <a href="https://instagram.com/vidracaria_top">Instagram</a>
                <a href="https://wa.me/5511999991111">WhatsApp</a>
            </body>
        </html>
        """
        raw_lead = {
            "Nome da Empresa": "Vidraçaria Top",
            "Telefone": "(11) 3344-5566",  # Landline in Google Maps
            "Site / Rede Social": "https://linktr.ee/vidracariatop",
            "Avaliação": "4.9⭐ (75)",
        }
        enriched = enrich_single_lead(raw_lead, niche="Vidraçaria")

        self.assertEqual(enriched["Tipo Presença"], "🔗 Link na Bio / Construtor Grátis")
        self.assertEqual(enriched["Email Extraído"], "orcamento@vidros.com.br")
        self.assertEqual(enriched["Instagram Extraído"], "@vidracaria_top")
        # Adopted embedded WhatsApp mobile from page sample
        self.assertEqual(enriched["phone_info"]["e164"], "5511999991111")
        self.assertTrue(enriched["WhatsApp 1-Clique"].startswith("https://wa.me/5511999991111"))
        self.assertEqual(enriched["Temperatura"], "🔥 Quente")

    @patch("enrichment.check_website_health")
    def test_enrich_leads_parallel(self, mock_health):
        mock_health.return_value = {
            "status": "✅ Site Operacional",
            "is_healthy": True,
            "has_https": True,
            "status_code": 200,
            "error": None,
            "url": "https://oficina.com.br",
        }

        leads = [
            {
                "Nome da Empresa": f"Empresa {i}",
                "Telefone": f"(11) 98765-432{i}",
                "Site / Rede Social": "Nenhum" if i % 2 == 0 else "https://oficina.com.br",
                "Avaliação": f"4.{i}⭐ ({i * 10})",
            }
            for i in range(5)
        ]

        results = enrich_leads_parallel(leads, max_workers=3, niche="Serviços Gerais")
        self.assertEqual(len(results), 5)
        for i, lead in enumerate(results):
            self.assertEqual(lead["Nome da Empresa"], f"Empresa {i}")
            self.assertIn("Score", lead)
            self.assertIn("Temperatura", lead)
            self.assertIn("WhatsApp 1-Clique", lead)
            self.assertIn("Tipo Presença", lead)


if __name__ == "__main__":
    unittest.main()
