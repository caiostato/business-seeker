"""
test_app_helpers.py - Unit tests for app.py helper functions
"""

import unittest
from app import get_diagnosis_badge, get_diagnosis_text, generate_lead_row_html


class TestAppHelpers(unittest.TestCase):

    def test_diagnosis_none(self):
        lead = {"web_presence": {"kind": "NONE"}}
        self.assertEqual(get_diagnosis_text(lead), "Sem Site")
        self.assertIn("Sem Site", get_diagnosis_badge(lead))

    def test_diagnosis_instagram(self):
        lead = {
            "web_presence": {"kind": "SOCIAL"},
            "websiteUri": "https://instagram.com/oficina"
        }
        self.assertEqual(get_diagnosis_text(lead), "Apenas Instagram")
        self.assertIn("Apenas Instagram", get_diagnosis_badge(lead))

    def test_diagnosis_linktree(self):
        lead = {
            "web_presence": {"kind": "LINKTREE_FREE"},
            "websiteUri": "https://linktr.ee/oficina"
        }
        self.assertEqual(get_diagnosis_text(lead), "Linktree")
        self.assertIn("Linktree", get_diagnosis_badge(lead))

    def test_diagnosis_site_offline(self):
        lead = {
            "web_presence": {"kind": "CUSTOM_DOMAIN"},
            "site_health": {"status": "⚠️ Site Fora do Ar"}
        }
        self.assertEqual(get_diagnosis_text(lead), "⚠️ Site Fora do Ar")
        self.assertIn("Fora do Ar", get_diagnosis_badge(lead))

    def test_diagnosis_site_insecure(self):
        lead = {
            "web_presence": {"kind": "CUSTOM_DOMAIN"},
            "site_health": {"status": "🔓 Sem HTTPS (Inseguro)"}
        }
        self.assertEqual(get_diagnosis_text(lead), "🔓 Sem HTTPS")
        self.assertIn("Sem HTTPS", get_diagnosis_badge(lead))

    def test_diagnosis_site_parked(self):
        lead = {
            "web_presence": {"kind": "CUSTOM_DOMAIN"},
            "site_health": {"status": "⚠️ Domínio Estacionado (GoDaddy)", "is_parked": True}
        }
        self.assertEqual(get_diagnosis_text(lead), "Domínio Estacionado (GoDaddy)")
        self.assertIn("Domínio Estacionado", get_diagnosis_badge(lead))

    def test_diagnosis_site_non_responsive(self):
        lead = {
            "web_presence": {"kind": "CUSTOM_DOMAIN"},
            "site_health": {"status": "📱 Site Não Responsivo (Redesign)", "is_redesign_candidate": True}
        }
        self.assertEqual(get_diagnosis_text(lead), "Site Não Responsivo (Redesign)")
        self.assertIn("Não Responsivo", get_diagnosis_badge(lead))

    def test_generate_lead_row_html(self):
        lead = {
            "Score": 85,
            "Temperatura": "🔥 Quente",
            "displayName": {"text": "Auto Mecânica Moema"},
            "is_seen": False,
            "Motivos Prioridade": "Alto volume de avaliações (45) • WhatsApp verificado",
            "web_presence": {"kind": "NONE"},
            "phone_info": {
                "formatted": "(11) 98765-4321",
                "is_mobile": True,
                "e164": "5511987654321",
                "type": "📱 Celular / WhatsApp"
            },
            "Instagram Extraído": "@automoema",
            "Email Extraído": "contato@automoema.com.br",
            "Avaliação": "4.8⭐ (45)",
            "Endereço": "Rua Canário, 100",
            "Google Maps": "https://maps.google.com/?cid=123"
        }
        html_row = generate_lead_row_html(lead)
        self.assertIn("85 pts", html_row)
        self.assertIn("🔥", html_row)
        self.assertIn("Auto Mecânica Moema", html_row)
        self.assertIn("🆕 Novo", html_row)
        self.assertIn("Sem Site", html_row)
        self.assertIn("(11) 98765-4321", html_row)
        self.assertIn("wa.me/5511987654321", html_row)
        self.assertIn("@automoema", html_row)
        self.assertIn("contato@automoema.com.br", html_row)
        self.assertIn("Rua Canário, 100", html_row)
        self.assertIn("https://maps.google.com/?cid=123", html_row)


if __name__ == "__main__":
    unittest.main()
