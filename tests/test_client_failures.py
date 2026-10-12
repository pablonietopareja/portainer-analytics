"""Upstream failures must produce bounded, non-sensitive application errors."""

import unittest
from unittest.mock import Mock

import requests

from engine import ApiError, Client


class UpstreamFailureTests(unittest.TestCase):
    def setUp(self):
        self.client = Client(
            {
                "url": "https://portainer.example.test",
                "token": "synthetic-token",
                "verify": True,
                "timeout": 3,
            }
        )
        self.session = Mock()
        self.client.local.session = self.session

    def test_unconfigured_client_does_not_connect(self):
        self.client.cfg["token"] = ""
        with self.assertRaisesRegex(ApiError, "Configure a Portainer server"):
            self.client.get("/api/endpoints")
        self.session.get.assert_not_called()

    def test_timeout_does_not_reveal_transport_details(self):
        self.session.get.side_effect = requests.Timeout("SYNTHETIC_PRIVATE_DETAILS")
        with self.assertRaisesRegex(ApiError, "^Request timed out$"):
            self.client.get("/api/endpoints")

    def test_transport_failure_does_not_reveal_transport_details(self):
        self.session.get.side_effect = requests.ConnectionError("SYNTHETIC_PRIVATE_DETAILS")
        with self.assertRaisesRegex(ApiError, "^Cannot connect to Portainer$"):
            self.client.get("/api/endpoints")

    def test_invalid_json_is_an_explicit_error(self):
        response = self.session.get.return_value
        response.status_code = 200
        response.json.side_effect = ValueError("SYNTHETIC_PRIVATE_DETAILS")
        with self.assertRaisesRegex(ApiError, "^Portainer returned a non-JSON response$"):
            self.client.get("/api/endpoints")

    def test_http_failures_do_not_echo_response_bodies(self):
        response = self.session.get.return_value
        response.text = "SYNTHETIC_PRIVATE_DETAILS"
        for status in (301, 401, 403, 429, 500, 502, 503):
            with self.subTest(status=status):
                response.status_code = status
                with self.assertRaises(ApiError) as error:
                    self.client.get("/api/endpoints")
                self.assertIn(str(status), str(error.exception))
                self.assertNotIn("SYNTHETIC_PRIVATE_DETAILS", str(error.exception))
        options = self.session.get.call_args.kwargs
        self.assertEqual(options["timeout"], (3, 3))
        self.assertTrue(options["verify"])
        self.assertFalse(options["allow_redirects"])

    def test_empty_optional_response_is_unavailable(self):
        self.session.get.return_value.status_code = 204
        self.assertIsNone(self.client.get("/api/endpoints/1/docker/v2/host/info"))


if __name__ == "__main__":
    unittest.main()
