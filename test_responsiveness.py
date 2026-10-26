"""
test_responsiveness.py - Unit test suite for responsiveness_auditor.py
"""

import unittest
from responsiveness_auditor import (
    audit_website_modernity,
    detect_legacy_technologies,
    detect_viewport,
    extract_copyright_year,
)


class TestResponsivenessAuditor(unittest.TestCase):
    """Test suite for Web Redesign Heuristic Engine."""

    def test_modern_responsive_website(self):
        """A modern, responsive, fast website should have 0 redesign opportunity score."""
        html = """
        <!DOCTYPE html>
        <html lang="pt-BR">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Clínica Odonto Moderna</title>
        </head>
        <body>
            <header><h1>Clínica Sorriso</h1></header>
            <main><p>Agende sua consulta conosco.</p></main>
            <footer>
                <p>&copy; 2026 Clínica Sorriso Ltda. Todos os direitos reservados.</p>
            </footer>
        </body>
        </html>
        """
        result = audit_website_modernity(html, latency_seconds=0.45, url="https://clinicasorriso.com.br")

        self.assertFalse(result["is_outdated_or_problematic"])
        self.assertTrue(result["has_viewport"])
        self.assertTrue(result["is_mobile_friendly"])
        self.assertFalse(result["is_slow"])
        self.assertFalse(result["has_legacy_tech"])
        self.assertEqual(result["copyright_year"], 2026)
        self.assertFalse(result["is_copyright_stale"])
        self.assertEqual(result["pain_points"], [])
        self.assertEqual(result["redesign_opportunity_score"], 0)
        self.assertEqual(result["url"], "https://clinicasorriso.com.br")

    def test_missing_viewport_tag(self):
        """Website without a viewport tag must be flagged as not mobile friendly."""
        html = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Auto Peças Silva</title>
        </head>
        <body>
            <h1>Auto Peças Silva</h1>
            <p>Tudo para seu carro.</p>
        </body>
        </html>
        """
        result = audit_website_modernity(html, latency_seconds=1.2)

        self.assertTrue(result["is_outdated_or_problematic"])
        self.assertFalse(result["has_viewport"])
        self.assertFalse(result["is_mobile_friendly"])
        self.assertIn("Sem viewport para celular", result["pain_points"])
        self.assertGreaterEqual(result["redesign_opportunity_score"], 15)

    def test_fixed_desktop_viewport(self):
        """Viewport tags with fixed desktop widths or user-scalable=no without device-width."""
        # Case 1: width=1024
        html_fixed = '<meta name="viewport" content="width=1024">'
        res1 = audit_website_modernity(html_fixed)
        self.assertTrue(res1["has_viewport"])
        self.assertFalse(res1["is_mobile_friendly"])
        self.assertIn("Viewport com largura fixa desktop", res1["pain_points"])

        # Case 2: width=1200 with user-scalable=no
        html_fixed_1200 = '<meta name="viewport" content="width=1200, user-scalable=no">'
        res2 = audit_website_modernity(html_fixed_1200)
        self.assertTrue(res2["has_viewport"])
        self.assertFalse(res2["is_mobile_friendly"])
        self.assertIn("Viewport com largura fixa desktop", res2["pain_points"])

        # Case 3: user-scalable=no without device-width
        html_no_device = '<meta name="viewport" content="user-scalable=no">'
        res3 = audit_website_modernity(html_no_device)
        self.assertTrue(res3["has_viewport"])
        self.assertFalse(res3["is_mobile_friendly"])
        self.assertIn("Viewport com largura fixa desktop", res3["pain_points"])

    def test_reversed_attribute_order_viewport(self):
        """Ensure meta tag attributes in reverse order (content before name) are properly detected."""
        html = '<meta content="width=device-width, initial-scale=1.0" name="viewport">'
        has_vp, mobile, content = detect_viewport(html)

        self.assertTrue(has_vp)
        self.assertTrue(mobile)
        self.assertEqual(content, "width=device-width, initial-scale=1.0")

    def test_legacy_technologies_frameset_and_frame(self):
        """Website using archaic frameset or frame tags must be flagged with legacy tech."""
        html = """
        <html>
        <frameset rows="80,*" frameborder="NO" border="0" framespacing="0">
            <frame name="topFrame" scrolling="NO" noresize src="header.htm">
            <frame name="mainFrame" src="content.htm">
        </frameset>
        </html>
        """
        has_legacy, items = detect_legacy_technologies(html)
        self.assertTrue(has_legacy)
        self.assertIn("Frameset", items)

        result = audit_website_modernity(html)
        self.assertTrue(result["has_legacy_tech"])
        self.assertIn("Tecnologias legadas (Flash/Frameset)", result["pain_points"])
        self.assertGreaterEqual(result["redesign_opportunity_score"], 10)

    def test_legacy_technologies_flash(self):
        """Flash embeds (.swf, application/x-shockwave-flash) must be flagged."""
        html_object = '<object classid="clsid:D27CDB6E-AE6D-11cf-96B8-444553540000" codebase="http://download.macromedia.com/pub/shockwave/cabs/flash/swflash.cab#version=6,0,29,0"><param name="movie" value="animacao.swf"></object>'
        html_embed = '<embed src="intro.swf" quality="high" type="application/x-shockwave-flash" width="600" height="400"></embed>'

        res1 = audit_website_modernity(html_object)
        self.assertTrue(res1["has_legacy_tech"])
        self.assertIn("Tecnologias legadas (Flash/Frameset)", res1["pain_points"])

        res2 = audit_website_modernity(html_embed)
        self.assertTrue(res2["has_legacy_tech"])
        self.assertIn("Tecnologias legadas (Flash/Frameset)", res2["pain_points"])

    def test_legacy_technologies_marquee_and_blink(self):
        """Obsolete tags like <marquee> and <blink> should be detected."""
        html = '<div><marquee>Ligue já para 11 99999-9999!</marquee><blink>Super Promoção</blink></div>'
        result = audit_website_modernity(html)

        self.assertTrue(result["has_legacy_tech"])
        self.assertIn("Tecnologias legadas (Tags obsoletas: marquee/blink)", result["pain_points"])

    def test_legacy_technologies_nested_tables(self):
        """Nested layout tables with cellpadding=0 and width=100% without modern CSS should be detected."""
        html = """
        <table width="100%" border="0" cellpadding="0" cellspacing="0">
            <tr>
                <td>
                    <table width="100%" border="0" cellpadding="0" cellspacing="0">
                        <tr><td>Layout Arcaico em Tabelas Aninhadas</td></tr>
                    </table>
                </td>
            </tr>
        </table>
        """
        result = audit_website_modernity(html)
        self.assertTrue(result["has_legacy_tech"])
        self.assertIn("Tecnologias legadas (Layout baseado em tabelas)", result["pain_points"])

    def test_modern_iframe_not_flagged_as_legacy(self):
        """A modern <iframe> (e.g. Google Maps, YouTube) must NOT be confused with archaic <frame>."""
        html = """
        <!DOCTYPE html>
        <html>
        <head><meta name="viewport" content="width=device-width, initial-scale=1"></head>
        <body>
            <iframe src="https://www.google.com/maps/embed?pb=123" width="600" height="450"></iframe>
        </body>
        </html>
        """
        has_legacy, items = detect_legacy_technologies(html)
        self.assertFalse(has_legacy)
        self.assertEqual(items, [])

    def test_stale_copyright_years(self):
        """Years older than or equal to (current_year - 4) should be flagged as stale."""
        # 2014
        html_2014 = "<footer>&copy; 2014 Serralheria Moderna. Todos os direitos reservados.</footer>"
        res_2014 = audit_website_modernity(html_2014, current_year=2026)
        self.assertEqual(res_2014["copyright_year"], 2014)
        self.assertTrue(res_2014["is_copyright_stale"])
        self.assertIn("Copyright desatualizado (2014)", res_2014["pain_points"])

        # 2017 with range
        html_2017 = "<div>Copyright 2010 - 2017 Marcenaria Express</div>"
        res_2017 = audit_website_modernity(html_2017, current_year=2026)
        self.assertEqual(res_2017["copyright_year"], 2017)
        self.assertTrue(res_2017["is_copyright_stale"])
        self.assertIn("Copyright desatualizado (2017)", res_2017["pain_points"])

        # 2020 (stale relative to 2026, as 2020 <= 2026 - 4)
        html_2020 = "<p>Copyright &copy; 2020 Contabilidade Santos</p>"
        res_2020 = audit_website_modernity(html_2020, current_year=2026)
        self.assertEqual(res_2020["copyright_year"], 2020)
        self.assertTrue(res_2020["is_copyright_stale"])
        self.assertIn("Copyright desatualizado (2020)", res_2020["pain_points"])

    def test_recent_copyright_not_stale(self):
        """A recent copyright year should not be flagged as stale."""
        html_recent = "<footer>© 2025 Nova Advocacia</footer>"
        year, is_stale = extract_copyright_year(html_recent, current_year=2026)
        self.assertEqual(year, 2025)
        self.assertFalse(is_stale)

        result = audit_website_modernity(html_recent, current_year=2026)
        self.assertFalse(result["is_copyright_stale"])
        self.assertNotIn("Copyright desatualizado", str(result["pain_points"]))

    def test_slow_latency_detection(self):
        """Latency >= 5.0s must trigger slow warning and pain point."""
        # Slow site (6.2s)
        res_slow = audit_website_modernity(
            '<meta name="viewport" content="width=device-width, initial-scale=1">',
            latency_seconds=6.2,
        )
        self.assertTrue(res_slow["is_slow"])
        self.assertEqual(res_slow["latency_seconds"], 6.2)
        self.assertIn("Carregamento muito lento (> 5s)", res_slow["pain_points"])
        self.assertGreaterEqual(res_slow["redesign_opportunity_score"], 5)

        # Fast site (1.1s)
        res_fast = audit_website_modernity(
            '<meta name="viewport" content="width=device-width, initial-scale=1">',
            latency_seconds=1.1,
        )
        self.assertFalse(res_fast["is_slow"])
        self.assertNotIn("Carregamento muito lento (> 5s)", res_fast["pain_points"])

    def test_opportunity_score_capping(self):
        """Total opportunity score must cap at 30 even if all pain points are triggered."""
        html_terrible = """
        <html>
        <head><title>Pior Site do Mundo</title></head>
        <frameset rows="100,*">
            <frame src="topo.htm">
            <frame src="corpo.htm">
        </frameset>
        <object type="application/x-shockwave-flash" data="banner.swf"></object>
        <footer>&copy; 2012 Empresa Falida</footer>
        </html>
        """
        # Triggers:
        # 1. No viewport (+15)
        # 2. Flash / Frameset (+10)
        # 3. Copyright 2012 (+5)
        # 4. Latency 7.5s (+5)
        # Raw sum = 35 -> Capped at 30
        result = audit_website_modernity(html_terrible, latency_seconds=7.5, current_year=2026)

        self.assertEqual(result["redesign_opportunity_score"], 30)
        self.assertTrue(result["is_outdated_or_problematic"])
        self.assertEqual(len(result["pain_points"]), 4)
        self.assertIn("Sem viewport para celular", result["pain_points"])
        self.assertIn("Tecnologias legadas (Flash/Frameset)", result["pain_points"])
        self.assertIn("Copyright desatualizado (2012)", result["pain_points"])
        self.assertIn("Carregamento muito lento (> 5s)", result["pain_points"])

    def test_empty_and_none_html_safety(self):
        """Passing None or empty string must not raise an exception."""
        res_empty = audit_website_modernity("", latency_seconds=0.0)
        self.assertIsInstance(res_empty, dict)
        self.assertFalse(res_empty["has_viewport"])
        self.assertFalse(res_empty["is_mobile_friendly"])

        res_none = audit_website_modernity(None, latency_seconds=5.5)  # type: ignore
        self.assertIsInstance(res_none, dict)
        self.assertTrue(res_none["is_slow"])
        self.assertIn("Carregamento muito lento (> 5s)", res_none["pain_points"])


if __name__ == "__main__":
    unittest.main()
