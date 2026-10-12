"""Public distribution security regressions using synthetic data and loopback HTTP."""

from __future__ import annotations

import os
import socket
import tempfile
import threading
import time
import unittest
from unittest import mock

import requests

import engine
import portainer_console as console
from persistence import Store


class NoNetworkClient:
    def __init__(self, cfg):
        self.cfg = dict(cfg)

    def get(self, *args, **kwargs):
        raise AssertionError("These tests must not contact an upstream server.")


class IdleCollector:
    def __init__(self, client, interval):
        self.client = client
        self.stop = threading.Event()

    def start(self):
        pass

    def close(self):
        self.stop.set()

    def snapshot(self):
        return {"sequence": 0, "status": "unconfigured", "environments": []}


class PublicSecurityTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="analytics-security-")
        self.addCleanup(temporary.cleanup)
        self.store = Store(temporary.name)
        for patcher in (
            mock.patch.dict(os.environ, {"CONSOLE_PUBLIC_URL": "", "CONSOLE_ALLOWED_HOSTS": ""}),
            mock.patch.object(engine, "Client", NoNetworkClient),
            mock.patch.object(engine, "Collector", IdleCollector),
            mock.patch.object(console.Manager, "observe", return_value=None),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)

    def manager(self):
        manager = console.Manager(self.store)
        self.addCleanup(manager.close)
        return manager

    def start_server(self, manager=None, **options):
        server = console.create_server("127.0.0.1", 0, manager or self.manager(), **options)
        thread = threading.Thread(
            target=server.serve_forever, kwargs={"poll_interval": 0.02}, daemon=True
        )
        thread.start()

        def stop():
            server.shutdown()
            server.server_close()
            thread.join(timeout=3)

        self.addCleanup(stop)
        self.url = f"http://127.0.0.1:{server.server_port}"
        self.server = server
        return server

    def request(self, method, path, **kwargs):
        with requests.Session() as client:
            client.trust_env = False
            return client.request(method, self.url + path, timeout=3, **kwargs)

    def test_clean_first_run_cannot_be_disabled_by_environment(self):
        with mock.patch.dict(
            os.environ,
            {
                "CONSOLE_STANDALONE": "false",
                "CONSOLE_REQUIRE_LOGIN": "false",
                "CONSOLE_ADMIN_PASSWORD": "Synthetic-unused-password",
                "PORTAINER_URL": "https://synthetic-unused.invalid",
                "PORTAINER_TOKEN": "synthetic-unused-token",
            },
        ):
            with mock.patch.object(engine, "config", wraps=engine.config) as config:
                manager = self.manager()
            config.assert_called_once_with(clean=True)
            self.assertTrue(manager.standalone)
            self.assertEqual(manager.cfg["url"], "")
            self.assertEqual(manager.cfg["token"], "")
            self.assertIsNone(self.store.setting("admin_password"))
            self.start_server(manager, local_admin=True)
            self.assertFalse(self.server.local_admin)
            session = self.request("GET", "/api/session").json()
            self.assertTrue(session["setup_required"])
            self.assertFalse(session["admin"])
            self.assertEqual(self.request("GET", "/api/settings").status_code, 401)

    def test_saved_connection_is_authoritative_without_bootstrap_reads(self):
        saved = {
            "url": "https://synthetic-saved.invalid",
            "token": "synthetic-saved-token",
            "verify": True,
            "timeout": 8,
        }
        self.store.set_setting("connection", saved)
        with mock.patch.object(
            engine, "config", side_effect=AssertionError("Unexpected bootstrap read")
        ):
            manager = self.manager()
        self.assertEqual(manager.cfg, saved)

    def test_factory_defaults_to_no_loopback_administrator(self):
        manager = self.manager()
        manager.standalone = False
        self.start_server(manager)
        self.assertFalse(self.server.local_admin)
        self.assertFalse(self.request("GET", "/api/session").json()["admin"])
        self.assertEqual(self.request("GET", "/api/snapshot").status_code, 401)

    def test_setup_sessions_are_bounded_and_valid_cookie_is_reused(self):
        self.start_server()
        self.server.max_sessions = 3
        first = self.request("GET", "/api/session").cookies["edge_session"]
        for _ in range(5):
            self.assertEqual(self.request("GET", "/api/session").status_code, 200)
        self.assertEqual(len(self.server.sessions), 3)
        self.assertNotIn(first, self.server.sessions)
        token = next(reversed(self.server.sessions))
        before = set(self.server.sessions)
        response = self.request("GET", "/api/session", headers={"Cookie": f"edge_session={token}"})
        self.assertNotIn("Set-Cookie", response.headers)
        self.assertEqual(set(self.server.sessions), before)

    def test_https_public_url_sets_secure_on_login_and_logout_cookie(self):
        password = "Synthetic-secure-cookie-password"
        self.store.set_setting("admin_password", console.password_hash(password))
        with mock.patch.dict(os.environ, {"CONSOLE_PUBLIC_URL": "https://analytics.example.test"}):
            self.start_server()
        response = self.request("POST", "/api/login", json={"password": password})
        self.assertEqual(response.status_code, 200)
        self.assertIn("; Secure", response.headers["Set-Cookie"])
        token = response.cookies["edge_session"]
        headers = {"Cookie": f"edge_session={token}", "X-Console-CSRF": response.json()["csrf"]}
        response = self.request("POST", "/api/logout", json={}, headers=headers)
        self.assertEqual(response.status_code, 200)
        self.assertIn("Max-Age=0", response.headers["Set-Cookie"])
        self.assertIn("; Secure", response.headers["Set-Cookie"])

    def test_forwarded_header_does_not_change_cookie_policy(self):
        self.start_server()
        response = self.request("GET", "/api/session", headers={"X-Forwarded-Proto": "https"})
        self.assertNotIn("; Secure", response.headers["Set-Cookie"])
        self.assertIn("HttpOnly", response.headers["Set-Cookie"])
        self.assertIn("SameSite=Strict", response.headers["Set-Cookie"])

    def test_request_limit_rejects_excess_connections_then_recovers(self):
        with mock.patch.object(console.ConsoleServer, "max_requests", 2):
            self.start_server()
        for _ in range(2):
            self.assertTrue(self.server.request_slots.acquire(blocking=False))
        try:
            try:
                response = self.request("GET", "/api/health")
            except requests.ConnectionError:
                # Closing an unread request can produce a TCP reset on Windows.
                pass
            else:
                self.assertEqual(response.status_code, 503)
                self.assertEqual(response.headers["Retry-After"], "5")
        finally:
            self.server.request_slots.release()
            self.server.request_slots.release()
        self.assertEqual(self.request("GET", "/api/health").status_code, 200)

    def test_stalled_request_is_closed_and_request_slot_released(self):
        with mock.patch.object(console.ConsoleServer, "max_requests", 1):
            self.start_server()
        self.server.request_timeout = 0.15
        with socket.create_connection(self.server.server_address, timeout=2) as client:
            client.settimeout(2)
            client.sendall(b"GET /api/health HTTP/1.1\r\nHost: 127.0.0.1\r\n")
            self.assertEqual(client.recv(1), b"")
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline:
            response = self.request("GET", "/api/health")
            if response.status_code == 200:
                break
            time.sleep(0.02)
        self.assertEqual(response.status_code, 200)

    def test_unauthorized_bodies_receive_an_http_error_without_reset(self):
        self.start_server()
        for size in (64, 4096, 65536):
            with self.subTest(size=size):
                response = self.request("POST", "/api/dashboards", json={"name": "x" * size})
                self.assertEqual(response.status_code, 401)
                self.assertIn("Administrator sign-in", response.json()["error"])

    def test_historical_device_hostnames_are_not_implicitly_trusted(self):
        self.start_server()
        for host in ("unknown-device.example.test", "unconfigured-host.example.test"):
            self.assertEqual(
                self.request("GET", "/api/health", headers={"Host": host}).status_code, 403
            )


if __name__ == "__main__":
    unittest.main()
