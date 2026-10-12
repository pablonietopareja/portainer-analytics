"""Isolated first-run tests: actual Manager/HTTP/SQLite, fake Portainer collector."""

import concurrent.futures
import os
import sqlite3
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

import requests

import engine
import portainer_console as console
from persistence import Conflict, Store

CONNECTION = {
    "url": "https://synthetic-portainer.invalid:9443",
    "token": "synthetic-test-token",
    "verify": True,
    "timeout": 2,
}
PASSWORD = "Synthetic-First-Run-Password"


class FakeClient:
    calls = []

    def __init__(self, cfg):
        self.cfg = dict(cfg)

    def get(self, path):
        type(self).calls.append((self.cfg["url"], path))
        if "unreachable" in self.cfg["url"]:
            raise engine.ApiError("Cannot connect to Portainer")
        return [{"Id": 1, "Name": "Synthetic environment"}]


class FakeCollector:
    def __init__(self, client, interval):
        self.client, self.interval = client, interval
        self.stop = threading.Event()
        self.started = False

    def start(self):
        self.started = True

    def close(self):
        self.stop.set()

    def snapshot(self):
        return {"sequence": 0, "status": "starting", "environments": []}


class FirstRunTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.store = Store(self.temporary.name)
        self.environment = mock.patch.dict(
            os.environ,
            {
                "CONSOLE_STANDALONE": "true",
                "PORTAINER_URL": "https://must-not-bootstrap.invalid",
                "PORTAINER_TOKEN": "synthetic-environment-secret",
                "PORTAINER_API_KEY": "synthetic-environment-api-key",
                "CONSOLE_ADMIN_PASSWORD": "Must-not-be-used-as-admin-password",
            },
        )
        self.environment.start()
        self.addCleanup(self.environment.stop)
        self.client_patch = mock.patch.object(engine, "Client", FakeClient)
        self.collector_patch = mock.patch.object(engine, "Collector", FakeCollector)
        self.observer_patch = mock.patch.object(console.Manager, "observe", return_value=None)
        for patcher in (self.client_patch, self.collector_patch, self.observer_patch):
            patcher.start()
            self.addCleanup(patcher.stop)
        FakeClient.calls = []
        self.manager = console.Manager(self.store)
        self.addCleanup(lambda: self.manager.close())
        # Deliberately request loopback auto-admin; standalone must override it.
        self.server = console.create_server("127.0.0.1", 0, self.manager, local_admin=True)
        self.worker = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.worker.start()
        self.addCleanup(self.stop_server)
        self.url = f"http://127.0.0.1:{self.server.server_port}"
        self.client = self.new_client()

    def stop_server(self):
        self.server.shutdown()
        self.server.server_close()
        self.worker.join(timeout=3)

    def new_client(self):
        client = requests.Session()
        client.trust_env = False
        self.addCleanup(client.close)
        return client

    def request(self, method, path, client=None, **kwargs):
        return (client or self.client).request(method, self.url + path, timeout=5, **kwargs)

    def setup_session(self, client=None):
        response = self.request("GET", "/api/session", client=client)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["setup_required"])
        self.assertFalse(data["admin"])
        self.assertFalse(data["login_available"])
        self.assertIn("HttpOnly", response.headers.get("Set-Cookie", ""))
        self.assertIn("SameSite=Strict", response.headers.get("Set-Cookie", ""))
        return {"X-Console-CSRF": data["csrf"]}

    def initialize(self, **overrides):
        headers = self.setup_session()
        return self.request(
            "POST",
            "/api/setup",
            json=dict(CONNECTION, password=PASSWORD, **overrides),
            headers=headers,
        )

    def test_clean_bootstrap_ignores_environment_and_never_reads_local_files(self):
        with mock.patch.object(
            Path, "read_text", side_effect=AssertionError("Local config was accessed")
        ):
            cfg = engine.config(clean=True)
        self.assertEqual(cfg, {"url": "", "token": "", "verify": True, "timeout": 8})
        self.assertEqual(self.manager.cfg, cfg)
        self.assertTrue(self.store.is_pristine())
        self.assertEqual(FakeClient.calls, [])
        self.assertFalse(self.server.local_admin)

    def test_setup_session_has_no_administrator_read_or_write_access(self):
        headers = self.setup_session()
        for path in ("/api/settings", "/api/snapshot", "/api/dashboards", "/api/catalog"):
            with self.subTest(path=path):
                self.assertEqual(self.request("GET", path).status_code, 401)
        for method, path in (
            ("PUT", "/api/settings"),
            ("POST", "/api/admin/password"),
            ("POST", "/api/dashboards"),
        ):
            with self.subTest(path=path):
                self.assertEqual(
                    self.request(method, path, json={}, headers=headers).status_code, 401
                )
        self.assertTrue(self.store.is_pristine())

    def test_setup_rejects_no_session_bad_csrf_and_foreign_origin(self):
        payload = dict(CONNECTION, password=PASSWORD)
        self.assertEqual(self.request("POST", "/api/setup", json=payload).status_code, 403)
        headers = self.setup_session()
        for extra in (
            {"X-Console-CSRF": "invalid"},
            {"Origin": "https://foreign.invalid"},
            {"Sec-Fetch-Site": "cross-site"},
        ):
            self.assertEqual(
                self.request(
                    "POST", "/api/setup", json=payload, headers=dict(headers, **extra)
                ).status_code,
                403,
            )
        self.assertTrue(self.store.is_pristine())
        self.assertEqual(FakeClient.calls, [])

    def test_failed_upstream_does_not_save_configuration_or_password(self):
        response = self.initialize(url="https://unreachable.invalid")
        self.assertEqual(response.status_code, 502)
        self.assertTrue(self.store.is_pristine())
        self.assertEqual(self.manager.cfg["url"], "")
        self.assertEqual(self.manager.cfg["token"], "")
        self.assertIsNone(self.store.setting("connection"))
        self.assertIsNone(self.store.setting("admin_password"))

    def test_invalid_setup_input_does_not_call_upstream_or_save_state(self):
        headers = self.setup_session()
        for values in (
            {"password": "short"},
            {"token": ""},
            {"verify": "false"},
            {"url": "file:///synthetic"},
        ):
            payload = dict(CONNECTION, password=PASSWORD)
            payload.update(values)
            self.assertEqual(
                self.request("POST", "/api/setup", json=payload, headers=headers).status_code, 400
            )
            self.assertTrue(self.store.is_pristine())
        self.assertEqual(FakeClient.calls, [])

    def test_success_initializes_once_and_returns_no_secret(self):
        response = self.initialize()
        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.json()["admin"])
        self.assertNotIn(CONNECTION["token"], response.text)
        self.assertNotIn(PASSWORD, response.text)
        self.assertEqual(self.store.setting("connection"), CONNECTION)
        digest = self.store.setting("admin_password")
        self.assertNotEqual(digest, PASSWORD)
        self.assertTrue(console.password_matches(PASSWORD, digest))
        self.assertEqual(self.store.dashboards(), [])
        self.assertEqual(self.request("GET", "/api/settings").status_code, 200)
        self.assertEqual(
            self.request(
                "POST",
                "/api/setup",
                json=dict(CONNECTION, password=PASSWORD),
                headers={"X-Console-CSRF": response.json()["csrf"]},
            ).status_code,
            409,
        )
        self.assertEqual(len(FakeClient.calls), 1)

    def test_other_setup_cookies_are_revoked_after_initialization(self):
        other = self.new_client()
        old_headers = self.setup_session(client=other)
        self.assertEqual(self.initialize().status_code, 201)
        data = self.request("GET", "/api/session", client=other).json()
        self.assertFalse(data["admin"])
        self.assertFalse(data["setup_required"])
        self.assertTrue(data["login_available"])
        self.assertIsNone(data["csrf"])
        self.assertEqual(self.request("GET", "/api/settings", client=other).status_code, 401)
        self.assertEqual(
            self.request(
                "POST",
                "/api/setup",
                client=other,
                json=dict(CONNECTION, password=PASSWORD),
                headers=old_headers,
            ).status_code,
            409,
        )

    def test_restart_keeps_configuration_and_requires_login(self):
        self.assertEqual(self.initialize().status_code, 201)
        self.manager.close()
        self.manager = console.Manager(Store(self.temporary.name))
        self.server.manager = self.manager
        self.server.sessions.clear()
        self.assertEqual(self.manager.cfg, CONNECTION)
        response = self.request("GET", "/api/session")
        self.assertFalse(response.json()["setup_required"])
        self.assertFalse(response.json()["admin"])
        self.assertEqual(
            self.request("POST", "/api/login", json={"password": PASSWORD}).status_code, 200
        )
        self.assertEqual(self.request("GET", "/api/settings").status_code, 200)

    def test_concurrent_http_setup_only_one_winner(self):
        clients = [self.new_client(), self.new_client()]
        headers = [self.setup_session(client=c) for c in clients]
        barrier = threading.Barrier(2)

        def claim(index):
            barrier.wait(timeout=3)
            body = dict(CONNECTION, password=PASSWORD + str(index))
            return self.request(
                "POST", "/api/setup", client=clients[index], json=body, headers=headers[index]
            ).status_code

        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(claim, range(2)))
        self.assertEqual(sorted(results), [201, 409])
        self.assertEqual(len(FakeClient.calls), 1)


class StoreInitializationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.store = Store(self.temporary.name)

    def test_sqlite_failure_rolls_back_connection_and_password_together(self):
        with self.store.connect() as db:
            db.execute(
                "CREATE TRIGGER synthetic_failure BEFORE INSERT ON settings WHEN NEW.key='admin_password' BEGIN SELECT RAISE(ABORT,'synthetic disk failure'); END"
            )
        with self.assertRaises(sqlite3.IntegrityError):
            self.store.initialize(CONNECTION, "synthetic-password-hash")
        self.assertTrue(self.store.is_pristine())
        self.assertIsNone(self.store.setting("connection"))
        self.assertIsNone(self.store.setting("admin_password"))

    def test_independent_store_connections_cannot_initialize_twice(self):
        stores = [self.store, Store(self.temporary.name)]
        barrier = threading.Barrier(2)

        def claim(index):
            barrier.wait(timeout=3)
            try:
                stores[index].initialize(
                    dict(CONNECTION, url=CONNECTION["url"] + str(index)), "hash" + str(index)
                )
                return index
            except Conflict:
                return None

        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(claim, range(2)))
        winners = [r for r in results if r is not None]
        self.assertEqual(len(winners), 1)
        winner = winners[0]
        self.assertEqual(self.store.setting("connection")["url"], CONNECTION["url"] + str(winner))
        self.assertEqual(self.store.setting("admin_password"), "hash" + str(winner))

    def test_existing_connection_admin_or_dashboard_disables_first_run(self):
        for key in ("connection", "admin_password"):
            with self.subTest(key=key), tempfile.TemporaryDirectory() as directory:
                store = Store(directory)
                store.set_setting(key, CONNECTION if key == "connection" else "synthetic-hash")
                self.assertFalse(store.is_pristine())
                with self.assertRaises(Conflict):
                    store.initialize(CONNECTION, "replacement-hash")
        self.store.save_dashboard({"name": "Existing synthetic dashboard"})
        self.assertFalse(self.store.is_pristine())
        with self.assertRaises(Conflict):
            self.store.initialize(CONNECTION, "replacement-hash")


if __name__ == "__main__":
    unittest.main()
