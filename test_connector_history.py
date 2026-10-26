"""
test_connector_history.py - Unit tests for history.py and scraper_connector.py.
"""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from unittest.mock import MagicMock, patch

import requests

import history
import scraper_connector


class TestHistory(unittest.TestCase):
    """Test suite for local seen-leads history manager."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.history_file = os.path.join(self.temp_dir.name, "leads_test.json")

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_load_history_missing_file(self):
        """Missing file should return empty dict without errors."""
        res = history.load_history(filepath=self.history_file)
        self.assertEqual(res, {})

    def test_load_history_empty_file(self):
        """Empty file should return empty dict without errors."""
        with open(self.history_file, "w", encoding="utf-8") as f:
            f.write("")
        res = history.load_history(filepath=self.history_file)
        self.assertEqual(res, {})

    def test_load_history_corrupted_json(self):
        """Corrupted JSON should fall back gracefully to empty dict."""
        with open(self.history_file, "w", encoding="utf-8") as f:
            f.write("{\ninvalid json syntax: [}")
        res = history.load_history(filepath=self.history_file)
        self.assertEqual(res, {})

    def test_load_history_non_dict_json(self):
        """JSON that is not a dictionary should fall back to empty dict."""
        with open(self.history_file, "w", encoding="utf-8") as f:
            f.write('["lead1", "lead2"]')
        res = history.load_history(filepath=self.history_file)
        self.assertEqual(res, {})

    def test_save_and_load_history_valid(self):
        """Valid dictionary should save and load identically."""
        sample = {
            "ChIJ123": {
                "id": "ChIJ123",
                "name": "Auto Mecânica Moema",
                "address": "Rua Canário, 100",
                "maps_uri": "https://maps.google.com/?cid=123",
                "seen_at": "2026-10-26T12:00:00Z"
            }
        }
        saved = history.save_history(sample, filepath=self.history_file)
        self.assertTrue(saved)
        loaded = history.load_history(filepath=self.history_file)
        self.assertEqual(loaded, sample)

    def test_mark_leads_as_seen_places_api_format(self):
        """Test marking leads using Google Places API schema."""
        leads = [
            {
                "id": "place_a",
                "displayName": {"text": "Oficina A"},
                "formattedAddress": "Av Paulista, 1000",
                "googleMapsUri": "https://maps.google.com/?cid=111",
            },
            {
                "id": "place_b",
                "displayName": {"text": "Oficina B"},
                "formattedAddress": "Av Paulista, 2000",
                "googleMapsUri": "https://maps.google.com/?cid=222",
            }
        ]
        marked_count = history.mark_leads_as_seen(leads, filepath=self.history_file)
        self.assertEqual(marked_count, 2)

        # Marking again should return 0 new leads
        re_marked = history.mark_leads_as_seen(leads, filepath=self.history_file)
        self.assertEqual(re_marked, 0)

        # Check recorded data
        stored = history.load_history(filepath=self.history_file)
        self.assertIn("place_a", stored)
        self.assertIn("place_b", stored)
        self.assertEqual(stored["place_a"]["name"], "Oficina A")
        self.assertEqual(stored["place_b"]["address"], "Av Paulista, 2000")
        self.assertIn("seen_at", stored["place_a"])

    def test_mark_leads_as_seen_app_format(self):
        """Test marking leads using app.py table column keys."""
        leads = [
            {
                "Nome da Empresa": "Vidraçaria Silva",
                "Endereço": "Rua Augusta, 500",
                "Google Maps": "https://maps.google.com/?cid=999",
                "id": "place_v1"
            }
        ]
        marked = history.mark_leads_as_seen(leads, filepath=self.history_file)
        self.assertEqual(marked, 1)

        stored = history.load_history(filepath=self.history_file)
        self.assertIn("place_v1", stored)
        self.assertEqual(stored["place_v1"]["name"], "Vidraçaria Silva")
        self.assertEqual(stored["place_v1"]["maps_uri"], "https://maps.google.com/?cid=999")

    def test_is_lead_seen(self):
        """Test lead detection by string ID, URI, or dictionary."""
        leads = [
            {
                "id": "cid_xyz",
                "displayName": {"text": "Pizzaria Napoli"},
                "formattedAddress": "Rua 1",
                "googleMapsUri": "https://maps.google.com/?cid=xyz"
            }
        ]
        history.mark_leads_as_seen(leads, filepath=self.history_file)

        # Check by ID string
        self.assertTrue(history.is_lead_seen("cid_xyz", filepath=self.history_file))
        # Check by URI string
        self.assertTrue(history.is_lead_seen("https://maps.google.com/?cid=xyz", filepath=self.history_file))
        # Check by lead dict
        self.assertTrue(history.is_lead_seen(leads[0], filepath=self.history_file))
        # Check unseen
        self.assertFalse(history.is_lead_seen("unknown_id", filepath=self.history_file))

    def test_filter_unseen_leads(self):
        """Test filtering out previously seen leads from a list."""
        lead_seen = {
            "id": "lead_1",
            "displayName": {"text": "Seen Business"},
            "formattedAddress": "Address 1",
        }
        lead_unseen_1 = {
            "id": "lead_2",
            "displayName": {"text": "New Business 1"},
            "formattedAddress": "Address 2",
        }
        lead_unseen_2 = {
            "id": "lead_3",
            "displayName": {"text": "New Business 2"},
            "formattedAddress": "Address 3",
        }

        # Record lead_1
        history.mark_leads_as_seen([lead_seen], filepath=self.history_file)

        # Filter candidates
        candidates = [lead_seen, lead_unseen_1, lead_unseen_2]
        unseen, filtered_count = history.filter_unseen_leads(candidates, filepath=self.history_file)

        self.assertEqual(filtered_count, 1)
        self.assertEqual(len(unseen), 2)
        self.assertEqual(unseen[0]["id"], "lead_2")
        self.assertEqual(unseen[1]["id"], "lead_3")

    def test_clear_history(self):
        """Test clearing history file."""
        leads = [{"id": "lead_1", "displayName": {"text": "Biz 1"}}]
        history.mark_leads_as_seen(leads, filepath=self.history_file)
        self.assertEqual(len(history.load_history(filepath=self.history_file)), 1)

        cleared = history.clear_history(filepath=self.history_file)
        self.assertTrue(cleared)
        self.assertEqual(history.load_history(filepath=self.history_file), {})


class TestScraperConnector(unittest.TestCase):
    """Test suite for google-maps-scraper connector."""

    @patch("scraper_connector.requests.get")
    def test_check_scraper_engine_status_online(self, mock_get):
        """Online status when engine responds 200."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_get.return_value = mock_resp

        status = scraper_connector.check_scraper_engine_status("http://127.0.0.1:8080")
        self.assertTrue(status["available"])
        self.assertIn("online", status["message"].lower())
        mock_get.assert_called_once_with("http://127.0.0.1:8080/api/v1/jobs", timeout=2)

    @patch("scraper_connector.requests.get")
    def test_check_scraper_engine_status_connection_error(self, mock_get):
        """Offline status when connection fails."""
        mock_get.side_effect = requests.exceptions.ConnectionError("Connection refused")

        status = scraper_connector.check_scraper_engine_status("http://127.0.0.1:8080")
        self.assertFalse(status["available"])
        self.assertIn("failed", status["message"].lower())

    @patch("scraper_connector.requests.get")
    def test_check_scraper_engine_status_timeout(self, mock_get):
        """Offline status when request times out."""
        mock_get.side_effect = requests.exceptions.Timeout("Request timed out")

        status = scraper_connector.check_scraper_engine_status("http://127.0.0.1:8080")
        self.assertFalse(status["available"])
        self.assertIn("timed out", status["message"].lower())

    @patch("scraper_connector.requests.get")
    def test_check_scraper_engine_status_http_error(self, mock_get):
        """Offline status when HTTP error returned."""
        mock_resp = MagicMock()
        mock_resp.status_code = 502
        mock_get.return_value = mock_resp

        status = scraper_connector.check_scraper_engine_status("http://127.0.0.1:8080")
        self.assertFalse(status["available"])
        self.assertIn("502", status["message"])

    def test_normalize_scraper_row(self):
        """Verify scraper row normalizes into Google Places API schema."""
        raw_row = {
            "place_id": "ChIJ_test_123",
            "title": "Marmoraria Central",
            "address": "Rua das Pedras, 123",
            "phone": "+55 11 99999-0000",
            "web_site": "https://marmoraria.exemplo.com",
            "review_rating": "4.8",
            "review_count": "150",
            "link": "https://maps.google.com/?cid=12345",
            "category": "marmoraria",
        }
        normalized = scraper_connector.normalize_scraper_row(raw_row)

        expected = {
            "id": "ChIJ_test_123",
            "displayName": {"text": "Marmoraria Central"},
            "formattedAddress": "Rua das Pedras, 123",
            "nationalPhoneNumber": "+55 11 99999-0000",
            "websiteUri": "https://marmoraria.exemplo.com",
            "rating": 4.8,
            "userRatingCount": 150,
            "googleMapsUri": "https://maps.google.com/?cid=12345",
            "businessStatus": "OPERATIONAL",
            "types": ["marmoraria"],
        }
        self.assertEqual(normalized, expected)

    def test_normalize_scraper_row_missing_fields(self):
        """Verify normalization handles empty / None / malformed fields cleanly."""
        raw_row = {
            "cid": "cid_999",
            "name": "Bar do Zé",
            "review_rating": "",
            "review_count": None,
        }
        normalized = scraper_connector.normalize_scraper_row(raw_row)

        self.assertEqual(normalized["id"], "cid_999")
        self.assertEqual(normalized["displayName"]["text"], "Bar do Zé")
        self.assertEqual(normalized["rating"], 0.0)
        self.assertEqual(normalized["userRatingCount"], 0)
        self.assertEqual(normalized["businessStatus"], "OPERATIONAL")
        self.assertEqual(normalized["types"], [])

    def test_dedupe_places_priority_1_id(self):
        """Duplicates sharing the same ID should be deduped."""
        places = [
            {"id": "id_1", "displayName": {"text": "Place 1"}, "formattedAddress": "Addr 1"},
            {"id": "id_1", "displayName": {"text": "Place 1 Duplicate"}, "formattedAddress": "Addr 1 Diff"},
            {"id": "id_2", "displayName": {"text": "Place 2"}, "formattedAddress": "Addr 2"},
        ]
        deduped = scraper_connector.dedupe_places(places)
        self.assertEqual(len(deduped), 2)
        self.assertEqual(deduped[0]["displayName"]["text"], "Place 1")
        self.assertEqual(deduped[1]["displayName"]["text"], "Place 2")

    def test_dedupe_places_priority_2_maps_uri(self):
        """When ID is empty, duplicates sharing googleMapsUri should be deduped."""
        places = [
            {"id": "", "googleMapsUri": "https://maps.google.com/?cid=100", "displayName": {"text": "A"}},
            {"id": "", "googleMapsUri": "https://maps.google.com/?cid=100", "displayName": {"text": "A Copy"}},
            {"id": "", "googleMapsUri": "https://maps.google.com/?cid=200", "displayName": {"text": "B"}},
        ]
        deduped = scraper_connector.dedupe_places(places)
        self.assertEqual(len(deduped), 2)
        self.assertEqual(deduped[0]["displayName"]["text"], "A")
        self.assertEqual(deduped[1]["displayName"]["text"], "B")

    def test_dedupe_places_priority_3_title_and_address(self):
        """When ID and mapsUri are empty, duplicates sharing title+address should be deduped."""
        places = [
            {"id": "", "googleMapsUri": "", "displayName": {"text": "Padaria Real "}, "formattedAddress": " Rua A, 10 "},
            {"id": "", "googleMapsUri": "", "displayName": {"text": " padaria real"}, "formattedAddress": "rua a, 10"},
            {"id": "", "googleMapsUri": "", "displayName": {"text": "Outra Padaria"}, "formattedAddress": "Rua B, 20"},
        ]
        deduped = scraper_connector.dedupe_places(places)
        self.assertEqual(len(deduped), 2)
        self.assertEqual(deduped[0]["displayName"]["text"], "Padaria Real ")
        self.assertEqual(deduped[1]["displayName"]["text"], "Outra Padaria")

    def test_dedupe_places_cross_priority(self):
        """Place with ID+URI should dedupe subsequent item matching the same URI even without ID."""
        places = [
            {"id": "id_alpha", "googleMapsUri": "https://maps.google.com/?cid=alpha", "displayName": {"text": "Alpha"}},
            {"id": "", "googleMapsUri": "https://maps.google.com/?cid=alpha", "displayName": {"text": "Alpha Duplicate"}},
        ]
        deduped = scraper_connector.dedupe_places(places)
        self.assertEqual(len(deduped), 1)
        self.assertEqual(deduped[0]["id"], "id_alpha")

    @patch("scraper_connector.time.sleep", return_value=None)
    @patch("scraper_connector.requests.get")
    @patch("scraper_connector.requests.post")
    def test_run_scraper_job_csv_success(self, mock_post, mock_get, mock_sleep):
        """Full scraper job lifecycle with CSV download."""
        # 1. POST /api/v1/jobs
        mock_post_resp = MagicMock()
        mock_post_resp.status_code = 201
        mock_post_resp.json.return_value = {"id": "test_job_123"}
        mock_post.return_value = mock_post_resp

        # 2. GET /api/v1/jobs/test_job_123 (status working -> completed)
        poll_working = MagicMock()
        poll_working.status_code = 200
        poll_working.json.return_value = {"status": "working"}

        poll_completed = MagicMock()
        poll_completed.status_code = 200
        poll_completed.json.return_value = {"status": "completed"}

        # 3. GET /api/v1/jobs/test_job_123/download
        download_resp = MagicMock()
        download_resp.status_code = 200
        download_resp.headers = {"Content-Type": "text/csv; charset=utf-8"}
        download_resp.text = (
            "place_id,title,address,phone,web_site,review_rating,review_count,link,category\n"
            "ChIJ_1,Oficina Alpha,Rua 1,1199991111,,4.5,20,https://maps.google.com/?cid=1,oficina\n"
            "ChIJ_2,Oficina Beta,Rua 2,1199992222,https://beta.com,4.0,10,https://maps.google.com/?cid=2,oficina\n"
            "ChIJ_1,Oficina Alpha,Rua 1,1199991111,,4.5,20,https://maps.google.com/?cid=1,oficina\n"
        )

        mock_get.side_effect = [poll_working, poll_completed, download_resp]

        progress_calls = []

        def on_progress(info):
            progress_calls.append(info.get("status"))

        results = scraper_connector.run_scraper_job(
            query="Oficina Mecânica Moema",
            lat=-23.60,
            lon=-46.66,
            max_results=10,
            progress_callback=on_progress,
            poll_interval=0.01,
        )

        # Verified deduplicated count: 2 (since ChIJ_1 was duplicated in CSV)
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]["id"], "ChIJ_1")
        self.assertEqual(results[0]["displayName"]["text"], "Oficina Alpha")
        self.assertEqual(results[1]["id"], "ChIJ_2")
        self.assertEqual(progress_calls, ["working", "completed"])

    @patch("scraper_connector.time.sleep", return_value=None)
    @patch("scraper_connector.requests.get")
    @patch("scraper_connector.requests.post")
    def test_run_scraper_job_json_success(self, mock_post, mock_get, mock_sleep):
        """Full scraper job lifecycle with JSON download."""
        mock_post_resp = MagicMock()
        mock_post_resp.status_code = 200
        mock_post_resp.json.return_value = {"id": "test_job_json"}
        mock_post.return_value = mock_post_resp

        poll_completed = MagicMock()
        poll_completed.status_code = 200
        poll_completed.json.return_value = {"status": "ok"}

        download_resp = MagicMock()
        download_resp.status_code = 200
        download_resp.headers = {"Content-Type": "application/json"}
        download_resp.json.return_value = [
            {
                "place_id": "place_json_1",
                "title": "Chaveiro 24h",
                "address": "Av Brasil, 50",
                "phone": "11988887777",
                "web_site": "",
                "review_rating": 4.9,
                "review_count": 35,
                "link": "https://maps.google.com/?cid=50",
                "category": "chaveiro"
            }
        ]

        mock_get.side_effect = [poll_completed, download_resp]

        results = scraper_connector.run_scraper_job(
            query="Chaveiro 24h",
            max_results=5,
            poll_interval=0.01,
        )

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["id"], "place_json_1")
        self.assertEqual(results[0]["displayName"]["text"], "Chaveiro 24h")
        self.assertEqual(results[0]["websiteUri"], "")

    @patch("scraper_connector.requests.post")
    def test_run_scraper_job_creation_failure(self, mock_post):
        """Job creation rejection raises RuntimeError."""
        mock_resp = MagicMock()
        mock_resp.status_code = 400
        mock_resp.text = "Invalid keyword"
        mock_post.return_value = mock_resp

        with self.assertRaises(RuntimeError):
            scraper_connector.run_scraper_job("test query")

    @patch("scraper_connector.time.sleep", return_value=None)
    @patch("scraper_connector.requests.get")
    @patch("scraper_connector.requests.post")
    def test_run_scraper_job_status_failure(self, mock_post, mock_get, mock_sleep):
        """Job marked as failed raises RuntimeError."""
        mock_post_resp = MagicMock()
        mock_post_resp.status_code = 200
        mock_post_resp.json.return_value = {"id": "failed_job"}
        mock_post.return_value = mock_post_resp

        poll_failed = MagicMock()
        poll_failed.status_code = 200
        poll_failed.json.return_value = {"status": "failed", "error": "Browser crashed"}

        mock_get.return_value = poll_failed

        with self.assertRaises(RuntimeError) as ctx:
            scraper_connector.run_scraper_job("query", poll_interval=0.01)
        self.assertIn("Browser crashed", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
