"""
test_smart_filters.py - Unit tests for smart_filters module.

Covers:
1. Franchise and chain detection by pattern (Shopping, Loja, Unidade, Filial, Express, etc.).
2. Network frequency detection in batch (e.g., 'Óticas Carol Moema' + 'Óticas Carol Pinheiros').
3. False-positive prevention for independent businesses ('Mecânica do Beto', 'Padaria Estrela de Moema').
4. Brazilian address normalization (abbreviations, numbers, CEP, and state cleaning).
5. Fuzzy deduplication with spelling variations, reordered tokens, and logradouro differences.
"""

import unittest

from smart_filters import (
    calculate_text_similarity,
    detect_chain_or_franchise,
    fuzzy_dedupe_places,
    normalize_brazilian_address,
    normalize_business_name,
    strip_accents,
)


class TestNormalizeBusinessName(unittest.TestCase):
    """Tests for business name normalization."""

    def test_empty_and_none(self):
        self.assertEqual(normalize_business_name(""), "")
        self.assertEqual(normalize_business_name(None), "")
        self.assertEqual(normalize_business_name("   "), "")

    def test_strip_accents_and_lowercase(self):
        res = normalize_business_name("Padaria Pão & Companhia")
        self.assertEqual(res, "padaria pao companhia")

    def test_remove_legal_entities(self):
        cases = [
            ("Oficina São José ME", "oficina sao jose"),
            ("Comércio Silva Ltda.", "comercio silva"),
            ("Auto Peças EPP", "auto pecas"),
            ("Hospital Central S/A", "hospital central"),
            ("Mecânica ABC EIRELI", "mecanica abc"),
        ]
        for inp, expected in cases:
            self.assertEqual(normalize_business_name(inp), expected)

    def test_remove_unit_and_district_suffixes(self):
        cases = [
            ("Óticas Carol Moema", "oticas carol"),
            ("Óticas Carol - Moema", "oticas carol"),
            ("Óticas Carol | Moema", "oticas carol"),
            ("Smart Fit - Unidade Jardins", "smart fit"),
            ("Smart Fit Pinheiros", "smart fit"),
            ("Drogaria São Paulo (Moema)", "drogaria sao paulo"),
            ("Auto Posto 3 Irmãos - Loja 02", "auto posto 3 irmaos"),
        ]
        for inp, expected in cases:
            self.assertEqual(normalize_business_name(inp), expected)

    def test_preserve_independent_names(self):
        self.assertEqual(normalize_business_name("Mecânica do Beto"), "mecanica do beto")
        self.assertEqual(normalize_business_name("Auto Elétrica São Jorge"), "auto eletrica sao jorge")


class TestNormalizeBrazilianAddress(unittest.TestCase):
    """Tests for Brazilian address standardization."""

    def test_empty_and_none(self):
        self.assertEqual(normalize_brazilian_address(""), "")
        self.assertEqual(normalize_brazilian_address(None), "")

    def test_paulista_variation_equivalence(self):
        addr1 = "Av. Paulista, 1000 - SP"
        addr2 = "Avenida Paulista, 1000, São Paulo"
        norm1 = normalize_brazilian_address(addr1)
        norm2 = normalize_brazilian_address(addr2)
        self.assertEqual(norm1, "avenida paulista, 1000")
        self.assertEqual(norm2, "avenida paulista, 1000")
        self.assertEqual(norm1, norm2)

    def test_santo_amaro_border_case(self):
        addr1 = "Av. Santo Amaro, 1200"
        addr2 = "Avenida Santo Amaro, 1200 - Vila Nova Conceição, São Paulo - SP"
        norm1 = normalize_brazilian_address(addr1)
        norm2 = normalize_brazilian_address(addr2)
        self.assertEqual(norm1, "avenida santo amaro, 1200")
        self.assertEqual(norm2, "avenida santo amaro, 1200")
        self.assertEqual(norm1, norm2)

    def test_street_abbreviations_expansion(self):
        cases = [
            ("R. Augusta, 500", "rua augusta, 500"),
            ("Rod. Raposo Tavares, 1500", "rodovia raposo tavares, 1500"),
            ("Al. Santos, 1437", "alameda santos, 1437"),
            ("Pça. da Sé, 10 - Centro", "praca da se, 10"),
            ("Dr. Arnaldo, 255", "doutor arnaldo, 255"),
            ("Est. do Campo Limpo, 300", "estrada do campo limpo, 300"),
            ("Tv. dos Pinheiros, 45", "travessa dos pinheiros, 45"),
        ]
        for inp, expected in cases:
            self.assertEqual(normalize_brazilian_address(inp), expected)

    def test_cep_and_country_removal(self):
        raw = "Rua Augusta, 500, Consolação, São Paulo - SP, 01305-000, Brasil"
        normalized = normalize_brazilian_address(raw)
        self.assertEqual(normalized, "rua augusta, 500")


class TestDetectChainOrFranchise(unittest.TestCase):
    """Tests for franchise, chain, and multi-unit network detection."""

    def test_empty_or_none(self):
        res = detect_chain_or_franchise("")
        self.assertFalse(res["is_likely_chain"])
        self.assertEqual(res["confidence"], 0.0)

    def test_shopping_pattern(self):
        names = [
            "Subway Shopping Morumbi",
            "Café do Shopping Ibirapuera",
            "Lojas Americanas Shopping Eldorado",
        ]
        for name in names:
            res = detect_chain_or_franchise(name)
            self.assertTrue(res["is_likely_chain"], f"Failed for {name}")
            self.assertGreaterEqual(res["confidence"], 0.85)
            self.assertIn("Shopping", res["matched_pattern"])

    def test_numbered_store_pattern(self):
        names = [
            "Drogasil Loja 04",
            "Farmácia Silva Loja 14",
            "Auto Peças Lj 02",
        ]
        for name in names:
            res = detect_chain_or_franchise(name)
            self.assertTrue(res["is_likely_chain"], f"Failed for {name}")
            self.assertGreaterEqual(res["confidence"], 0.90)
            self.assertIn("Loja", res["matched_pattern"])

    def test_unit_and_branch_pattern(self):
        # Unidade
        res_unidade = detect_chain_or_franchise("Clínica Sorriso Unidade Moema")
        self.assertTrue(res_unidade["is_likely_chain"])
        self.assertIn("Unidade", res_unidade["matched_pattern"])

        # Filial
        res_filial = detect_chain_or_franchise("Distribuidora ABC Filial 02")
        self.assertTrue(res_filial["is_likely_chain"])
        self.assertIn("Filial", res_filial["matched_pattern"])

    def test_express_and_autoposto_patterns(self):
        # Express
        res_exp = detect_chain_or_franchise("Cacau Show Express")
        self.assertTrue(res_exp["is_likely_chain"])
        self.assertGreaterEqual(res_exp["confidence"], 0.85)

        # Auto Posto
        res_posto = detect_chain_or_franchise("Auto Posto Shell Moema")
        self.assertTrue(res_posto["is_likely_chain"])

        # Rede
        res_rede = detect_chain_or_franchise("Rede Drogal Santana")
        self.assertTrue(res_rede["is_likely_chain"])

        # Atacadão / Supermercado
        res_atacadao = detect_chain_or_franchise("Atacadão Morumbi")
        self.assertTrue(res_atacadao["is_likely_chain"])

    def test_known_brand_catalog(self):
        brands = [
            "Smart Fit Moema",
            "Óticas Carol",
            "Burger King",
            "Subway",
            "Drogasil",
            "Cacau Show",
        ]
        for b in brands:
            res = detect_chain_or_franchise(b)
            self.assertTrue(res["is_likely_chain"], f"Known brand '{b}' not flagged")
            self.assertGreaterEqual(res["confidence"], 0.90)

    def test_batch_frequency_network_detection(self):
        batch = [
            "Óticas Carol Moema",
            "Óticas Carol Pinheiros",
            "Mecânica do Beto",
            "Padaria Estrela de Moema",
        ]
        # Both units of Óticas Carol must be flagged by batch repetition
        res_carol1 = detect_chain_or_franchise(batch[0], all_batch_names=batch)
        res_carol2 = detect_chain_or_franchise(batch[1], all_batch_names=batch)

        self.assertTrue(res_carol1["is_likely_chain"])
        self.assertIn("múltiplas unidades", res_carol1["matched_pattern"])
        self.assertGreaterEqual(res_carol1["confidence"], 0.90)

        self.assertTrue(res_carol2["is_likely_chain"])
        self.assertIn("múltiplas unidades", res_carol2["matched_pattern"])

    def test_independent_businesses_not_flagged(self):
        """Ensure local independent SMBs are NOT falsely flagged as chains."""
        independent_batch = [
            "Mecânica do Beto",
            "Padaria Estrela de Moema",
            "Padaria Central",
            "Auto Elétrica São Jorge",
            "Bar do Zé",
            "Restaurante Sabor Caseiro",
        ]
        for name in independent_batch:
            res = detect_chain_or_franchise(name, all_batch_names=independent_batch)
            self.assertFalse(
                res["is_likely_chain"],
                f"Independent business '{name}' was falsely flagged as chain: {res}",
            )
            self.assertEqual(res["confidence"], 0.0)


class TestFuzzyDedupePlaces(unittest.TestCase):
    """Tests for fuzzy deduplication on places lists."""

    def test_empty_list(self):
        deduped, removed = fuzzy_dedupe_places([])
        self.assertEqual(deduped, [])
        self.assertEqual(removed, 0)

    def test_exact_id_deduplication(self):
        places = [
            {"id": "place_123", "displayName": {"text": "Oficina São José"}, "formattedAddress": "Rua A, 10"},
            {"id": "place_123", "displayName": {"text": "Oficina São José"}, "formattedAddress": "Rua A, 10"},
        ]
        deduped, removed = fuzzy_dedupe_places(places)
        self.assertEqual(len(deduped), 1)
        self.assertEqual(removed, 1)

    def test_exact_uri_deduplication(self):
        places = [
            {"id": "", "googleMapsUri": "https://maps.google.com/?cid=999", "displayName": "Loja A"},
            {"id": "", "googleMapsUri": "https://maps.google.com/?cid=999", "displayName": "Loja A (Cópia)"},
        ]
        deduped, removed = fuzzy_dedupe_places(places)
        self.assertEqual(len(deduped), 1)
        self.assertEqual(removed, 1)

    def test_fuzzy_dedupe_moema_itaim_border_variation(self):
        """
        The classic cross-neighborhood search duplication problem:
        One query returns 'Oficina Mecânica São José' at 'Av. Santo Amaro, 1200',
        another returns 'Oficina São José Mecânica' at 'Avenida Santo Amaro, 1200 - Vila Nova Conceição, SP'.
        Both must be deduplicated into a single lead.
        """
        places = [
            {
                "id": "ChIJ_AAA111",
                "displayName": {"text": "Oficina Mecânica São José"},
                "formattedAddress": "Av. Santo Amaro, 1200",
            },
            {
                "id": "ChIJ_BBB222",
                "displayName": {"text": "Oficina São José Mecânica"},
                "formattedAddress": "Avenida Santo Amaro, 1200 - Vila Nova Conceição, São Paulo - SP",
            },
            {
                "id": "ChIJ_CCC333",
                "displayName": {"text": "Mecânica do Beto"},
                "formattedAddress": "Rua Clodomiro Amazonas, 500",
            },
        ]
        deduped, removed = fuzzy_dedupe_places(places)
        self.assertEqual(len(deduped), 2)
        self.assertEqual(removed, 1)
        self.assertEqual(deduped[0]["displayName"]["text"], "Oficina Mecânica São José")
        self.assertEqual(deduped[1]["displayName"]["text"], "Mecânica do Beto")

    def test_fuzzy_dedupe_spelling_typo(self):
        places = [
            {
                "id": "p1",
                "displayName": {"text": "Auto Elétrica Central"},
                "formattedAddress": "Rua Augusta, 100",
            },
            {
                "id": "p2",
                "displayName": {"text": "Auto Eletrica Centraal"},
                "formattedAddress": "R. Augusta, 100",
            },
        ]
        deduped, removed = fuzzy_dedupe_places(places)
        self.assertEqual(len(deduped), 1)
        self.assertEqual(removed, 1)

    def test_different_businesses_at_distinct_addresses(self):
        places = [
            {
                "id": "p1",
                "displayName": {"text": "Oficina do Beto"},
                "formattedAddress": "Rua Augusta, 100",
            },
            {
                "id": "p2",
                "displayName": {"text": "Padaria Estrela de Moema"},
                "formattedAddress": "Alameda dos Arapanés, 800",
            },
        ]
        deduped, removed = fuzzy_dedupe_places(places)
        self.assertEqual(len(deduped), 2)
        self.assertEqual(removed, 0)

    def test_different_businesses_at_same_building(self):
        """
        Two entirely different businesses located in the same building / street address
        must NOT be deduplicated.
        """
        places = [
            {
                "id": "p1",
                "displayName": {"text": "Smart Fit"},
                "formattedAddress": "Av. Paulista, 1000",
            },
            {
                "id": "p2",
                "displayName": {"text": "Drogasil"},
                "formattedAddress": "Av. Paulista, 1000",
            },
        ]
        deduped, removed = fuzzy_dedupe_places(places)
        self.assertEqual(len(deduped), 2)
        self.assertEqual(removed, 0)


if __name__ == "__main__":
    unittest.main()
