"""Regression tests using temporary SQLite files and loopback fake servers."""

from __future__ import annotations

import copy
import gc
import json
import sys
import tempfile
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import requests

import engine
import portainer_console as console
from dashboard_metrics import metric_catalog, metric_values, validate_dashboard
from persistence import Conflict, Store


def definition(**changes):
    result = {
        "name": "Synthetic dashboard",
        "description": "Selected telemetry only",
        "source_id": "synthetic-source",
        "environment_id": 3,
        "range_minutes": 15,
        "refresh_seconds": 5,
        "theme": "dark",
        "widgets": [
            {
                "id": "cpu-panel",
                "title": "Selected CPU",
                "kind": "container",
                "sources": ["selected"],
                "metric": "cpu_percent",
                "visual": "line",
                "width": 6,
                "height": 260,
                "aggregate": "compare",
                "color": "green",
                "min": 0,
                "max": 100,
                "threshold": None,
            }
        ],
    }
    result.update(changes)
    return result


def snapshot():
    stamp = engine.utcnow()

    def container(name, cpu):
        return {
            "id": ("a" if name == "selected" else "b") * 64,
            "name": name,
            "state": "running",
            "stack": "selected-stack",
            "networks": [{"name": "selected-network"}],
            "writable_bytes": 12,
            "stats": {
                "cpu_percent": cpu,
                "memory_bytes": 200,
                "rx_rate": 3,
                "tx_rate": 4,
                "pids": 2,
                "cache_bytes": 20,
            },
        }

    env = {
        "id": 3,
        "name": "Synthetic environment",
        "status": "live",
        "updated_at": stamp,
        "host": {"name": "PRIVATE_HOST_MARKER", "docker_root": "PRIVATE_PATH_MARKER"},
        "containers": [container("selected", 25), container("PRIVATE_CONTAINER_MARKER", 75)],
        "stacks": [{"name": "selected-stack"}],
        "networks": [{"name": "selected-network"}],
        "metrics": {"cpu_percent": 100, "memory_bytes": 400},
        "storage": {"layers_bytes": 1000, "cache_bytes": 40},
        "inspect": {"Env": ["PRIVATE_ENV_MARKER"]},
        "logs": "PRIVATE_LOG_MARKER",
    }
    return {
        "status": "live",
        "sequence": 1,
        "generation": "generation-one",
        "source_id": "synthetic-source",
        "updated_at": stamp,
        "environments": [env],
    }


class FakeManager:
    """Use the real projection implementation without constructing collectors."""

    dashboard_data = console.Manager.dashboard_data

    def __init__(self, store):
        self.store, self.lock = store, threading.RLock()
        self.interval, self.recent = 5, {}
        self.value = snapshot()
        self.generation = self.value["generation"]
        self.collector = mock.Mock()
        self.collector.snapshot.side_effect = self.snapshot
        self.collector.docker.side_effect = AssertionError("No real upstream calls are allowed")

    def snapshot(self):
        return copy.deepcopy(self.value)

    def connection_public(self):
        return {
            "url": "https://synthetic.invalid",
            "has_token": True,
            "verify": True,
            "timeout": 8,
            "source_id": "synthetic-source",
        }


class TemporaryStoreTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="portainer-console-test-")
        self.store = Store(self.temporary.name)

    def tearDown(self):
        # sqlite connection contexts may defer handle release until garbage collection.
        self.store = None
        gc.collect()
        self.temporary.cleanup()


class PersistenceTests(TemporaryStoreTest):
    def test_restart_preserves_dashboard_settings_and_selected_history(self):
        saved = self.store.save_dashboard(validate_dashboard(definition()))
        self.store.set_setting("synthetic_setting", {"enabled": True})
        self.store.record(
            [
                (
                    "synthetic-source",
                    3,
                    "container",
                    "selected",
                    1000,
                    json.dumps({"cpu_percent": 25}),
                )
            ]
        )
        restarted = Store(self.temporary.name)
        self.assertEqual(restarted.dashboard(saved["id"])["name"], saved["name"])
        self.assertEqual(restarted.setting("synthetic_setting"), {"enabled": True})
        self.assertEqual(
            restarted.history("synthetic-source", 3, "container", "selected", 0),
            [(1000, {"cpu_percent": 25})],
        )

    def test_revision_update_and_delete_reject_stale_writes(self):
        first = self.store.save_dashboard(validate_dashboard(definition()))
        changed = validate_dashboard(definition(name="Updated dashboard"))
        second = self.store.save_dashboard(changed, first["id"], first["revision"])
        self.assertEqual(second["revision"], 2)
        with self.assertRaises(Conflict):
            self.store.save_dashboard(changed, first["id"], first["revision"])
        with self.assertRaises(Conflict):
            self.store.delete_dashboard(first["id"], first["revision"])
        self.assertEqual(self.store.dashboard(first["id"])["revision"], 2)
        self.store.delete_dashboard(first["id"], second["revision"])
        self.assertIsNone(self.store.dashboard(first["id"]))

    def test_separate_store_instances_enforce_revision_conflicts(self):
        first = self.store.save_dashboard(validate_dashboard(definition()))
        other = Store(self.temporary.name)
        self.store.save_dashboard(
            validate_dashboard(definition(name="First writer")), first["id"], 1
        )
        with self.assertRaises(Conflict):
            other.save_dashboard(
                validate_dashboard(definition(name="Second writer")), first["id"], 1
            )

    def test_share_enable_restart_rotate_and_revoke(self):
        saved = self.store.save_dashboard(validate_dashboard(definition()))
        token = self.store.share(saved["id"])
        self.assertEqual(token, self.store.share(saved["id"]))
        self.assertNotIn(token, json.dumps(self.store.dashboards()))
        self.assertEqual(
            Store(self.temporary.name).dashboard(token, shared=True)["id"], saved["id"]
        )
        replacement = self.store.share(saved["id"], "rotate")
        self.assertNotEqual(token, replacement)
        self.assertIsNone(self.store.dashboard(token, shared=True))
        self.assertIsNotNone(self.store.dashboard(replacement, shared=True))
        self.store.share(saved["id"], "disable")
        self.assertIsNone(self.store.dashboard(replacement, shared=True))

    def test_delete_revokes_the_share(self):
        saved = self.store.save_dashboard(validate_dashboard(definition()))
        token = self.store.share(saved["id"])
        self.store.delete_dashboard(saved["id"], saved["revision"])
        self.assertIsNone(self.store.dashboard(token, shared=True))

    def test_history_keys_isolate_source_environment_kind_and_resource(self):
        rows = [
            (source, eid, kind, name, 1000, json.dumps({"cpu_percent": value}))
            for source, eid, kind, name, value in [
                ("wanted", 3, "container", "selected", 10),
                ("other-source", 3, "container", "selected", 20),
                ("wanted", 13, "container", "selected", 30),
                ("wanted", 3, "stack", "selected", 40),
                ("wanted", 3, "container", "other-resource", 50),
            ]
        ]
        self.store.record(rows)
        self.assertEqual(
            self.store.history("wanted", 3, "container", "selected", 0),
            [(1000, {"cpu_percent": 10})],
        )

    def test_history_is_bounded_retains_latest_and_prunes(self):
        self.store.record(
            [
                ("s", 3, "container", "selected", i, json.dumps({"cpu_percent": i}))
                for i in range(1001)
            ]
        )
        history = self.store.history("s", 3, "container", "selected", 0)
        self.assertLessEqual(len(history), 361)
        self.assertEqual(history[-1][0], 1000)
        self.store.prune(900)
        self.assertTrue(
            all(t >= 900 for t, _ in self.store.history("s", 3, "container", "selected", 0))
        )


class SchemaTests(unittest.TestCase):
    def test_native_metric_survives_unavailable_source_and_rejects_sum(self):
        raw = definition()
        raw["widgets"][0]["metric"] = "raw.networks.eth0.rx_packets"
        validated = validate_dashboard(raw)
        self.assertIn(
            raw["widgets"][0]["metric"],
            metric_catalog({"environments": []}, [validated])["metrics"],
        )
        raw["widgets"][0].update(sources=["selected", "other"], aggregate="sum")
        with self.assertRaises(ValueError):
            validate_dashboard(raw)

    def test_image_volume_and_node_metric_bindings(self):
        env = {
            "images": [{"id": "sha256:example", "size": 120, "shared_size": 80, "containers": 2}],
            "volumes": [{"name": "volume", "size": None, "references": 1}],
            "nodes": [
                {
                    "name": "node",
                    "resources": {"NanoCPUs": 4000000000, "MemoryBytes": 4000},
                    "status": "ready",
                }
            ],
        }
        self.assertEqual(metric_values(env, "image", "sha256:example")["image_bytes"], 120)
        self.assertIsNone(metric_values(env, "volume", "volume")["volume_size_bytes"])
        self.assertEqual(metric_values(env, "node", "node")["node_cpus"], 4)
        self.assertIsNone(metric_values(env, "node", "missing"))

    def test_inspect_metadata_does_not_copy_secrets(self):
        raw = {
            "RestartCount": 3,
            "State": {
                "Running": False,
                "OOMKilled": True,
                "Health": {"Status": "unhealthy", "Log": [{"Output": "SECRET"}]},
            },
            "Config": {"Env": ["SECRET=value"]},
            "HostConfig": {"Memory": 0, "NanoCpus": 2000000000, "PidsLimit": -1},
        }
        result = engine.container_metadata(raw)
        self.assertNotIn("SECRET", json.dumps(result))
        self.assertEqual(
            (result["restart_count"], result["unhealthy"], result["cpu_limit_cores"]), (3, 1, 2)
        )
        self.assertIsNone(result["uptime_seconds"])
        self.assertIsNone(result["pids_configured_limit"])

    def test_chart_reduction_keeps_explicit_outages_and_latest(self):
        points = [{"t": i * 5000, "v": 12} for i in range(2000)]
        points[817]["v"] = None
        reduced = console.chart_points(points, 30000)
        self.assertLessEqual(len(reduced), 361)
        self.assertTrue(any(p["v"] is None for p in reduced))
        self.assertEqual(reduced[-1], points[-1])

    def test_chart_marks_unobserved_time_gaps(self):
        reduced = console.chart_points([{"t": 1000, "v": 12}, {"t": 90000, "v": 14}], 30000)
        self.assertEqual(
            reduced, [{"t": 1000, "v": 12}, {"t": 31000, "v": None}, {"t": 90000, "v": 14}]
        )

    def test_validation_normalizes_only_allowlisted_definition_fields(self):
        raw = definition(name="  Name  ")
        raw["private_configuration"] = "SYNTHETIC_PRIVATE"
        raw["widgets"][0]["private_token"] = "SYNTHETIC_PRIVATE"
        result = validate_dashboard(raw)
        self.assertEqual(result["name"], "Name")
        self.assertNotIn("SYNTHETIC_PRIVATE", json.dumps(result))

    def test_resource_names_deduplicate(self):
        raw = definition()
        raw["widgets"][0]["sources"] = ["selected", "selected"]
        self.assertEqual(validate_dashboard(raw)["widgets"][0]["sources"], ["selected"])

    def test_invalid_dashboard_fields_rejected(self):
        for patch in [
            {"name": ""},
            {"name": "x" * 101},
            {"description": "x" * 501},
            {"source_id": ""},
            {"environment_id": True},
            {"environment_id": 0},
            {"widgets": {}},
            {"widgets": [definition()["widgets"][0]] * 65},
            {"range_minutes": 7},
            {"refresh_seconds": 1},
            {"theme": "unknown"},
        ]:
            with self.subTest(fields=list(patch)), self.assertRaises((ValueError, TypeError)):
                validate_dashboard(definition(**patch))

    def test_invalid_panel_fields_rejected(self):
        for patch in [
            {"kind": "host-shell"},
            {"metric": "command"},
            {"sources": []},
            {"sources": ["x"] * 17},
            {"sources": [None]},
            {"id": "../escape"},
            {"title": ""},
            {"visual": "html"},
            {"width": 13},
            {"height": 1},
            {"aggregate": "eval"},
            {"color": "url(unsafe)"},
            {"min": float("nan")},
            {"max": float("inf")},
            {"threshold": True},
            {"max": 0},
        ]:
            raw = definition()
            raw["widgets"][0].update(patch)
            with self.subTest(fields=list(patch)), self.assertRaises((ValueError, TypeError)):
                validate_dashboard(raw)

    def test_duplicate_panel_ids_rejected(self):
        raw = definition()
        raw["widgets"].append(copy.deepcopy(raw["widgets"][0]))
        with self.assertRaises(ValueError):
            validate_dashboard(raw)

    def test_missing_and_stopped_resource_telemetry_is_not_invented(self):
        env = snapshot()["environments"][0]
        self.assertIsNone(metric_values(env, "container", "missing"))
        env["containers"][0]["state"] = "exited"
        metrics = metric_values(env, "container", "selected")
        self.assertIsNone(metrics["cpu_percent"])
        self.assertEqual(metrics["running"], 0)
        self.assertEqual(metrics["total"], 1)


class ProjectionTests(TemporaryStoreTest):
    def test_sum_precedes_downsampling_for_different_resource_start_times(self):
        now = time.time()
        rows = [
            (
                "synthetic-source",
                3,
                "container",
                name,
                now - (1000 - i) * 5,
                json.dumps({"cpu_percent": 10}),
            )
            for name, start in (("selected", 0), ("second", 1))
            for i in range(start, 1000)
        ]
        self.store.record(rows)
        raw = definition(range_minutes=1440)
        raw["widgets"][0].update(sources=["selected", "second"], aggregate="sum")
        manager = FakeManager(self.store)
        manager.value["status"] = "offline"
        points = manager.dashboard_data(validate_dashboard(raw))["widgets"][0]["series"][0][
            "points"
        ]
        self.assertLessEqual(len(points), 361)
        self.assertGreater(sum(p["v"] == 20 for p in points), 300)
        self.assertTrue(any(p["v"] is None for p in points))

    def test_public_projection_has_only_selected_metrics(self):
        manager = FakeManager(self.store)
        result = manager.dashboard_data(validate_dashboard(definition()))
        text = json.dumps(result)
        self.assertNotIn("PRIVATE_", text)
        self.assertNotIn("source_id", result)
        self.assertNotIn("environment_id", result)
        self.assertEqual(len(result["widgets"]), 1)
        series = result["widgets"][0]["series"]
        self.assertEqual([s["name"] for s in series], ["selected"])
        self.assertEqual(series[0]["value"], 25)
        self.assertEqual(set(series[0]), {"name", "value", "points"})

    def test_different_source_cannot_supply_current_or_history_metrics(self):
        manager = FakeManager(self.store)
        manager.value["source_id"] = "different-source"
        stamp = time.time()
        self.store.record(
            [
                (
                    "different-source",
                    3,
                    "container",
                    "selected",
                    stamp,
                    json.dumps({"cpu_percent": 987654}),
                )
            ]
        )
        result = manager.dashboard_data(validate_dashboard(definition()))
        self.assertEqual(result["status"], "unavailable")
        self.assertIsNone(result["environment_name"])
        self.assertIsNone(result["widgets"][0]["series"][0]["value"])
        self.assertNotIn("987654", json.dumps(result))

    def test_stale_or_offline_snapshot_does_not_report_current_values(self):
        for offline in (False, True):
            manager = FakeManager(self.store)
            if offline:
                manager.value["status"] = "offline"
            else:
                manager.value["environments"][0]["updated_at"] = "2000-01-01T00:00:00+00:00"
            with self.subTest(offline=offline):
                result = manager.dashboard_data(validate_dashboard(definition()))
                self.assertEqual(result["status"], "unavailable")
                self.assertIsNone(result["widgets"][0]["series"][0]["value"])

    def test_aggregate_keeps_missing_data_unknown(self):
        raw = definition()
        raw["widgets"][0].update(sources=["selected", "missing"], aggregate="sum")
        series = FakeManager(self.store).dashboard_data(validate_dashboard(raw))["widgets"][0][
            "series"
        ]
        self.assertEqual(len(series), 1)
        self.assertIsNone(series[0]["value"])


class ConnectionTests(unittest.TestCase):
    def setUp(self):
        self.previous = {
            "url": "https://example.invalid/tenant",
            "token": "SYNTHETIC_RETAINED_TOKEN",
            "verify": True,
            "timeout": 8,
        }

    def test_blank_token_retained_only_for_identical_server(self):
        raw = {"url": self.previous["url"], "token": "", "verify": True, "timeout": 8}
        self.assertEqual(
            console.validate_connection(raw, self.previous)["token"], self.previous["token"]
        )
        for url in ("https://other.invalid/tenant", "https://example.invalid/other"):
            with self.subTest(url=url), self.assertRaises(ValueError):
                console.validate_connection(dict(raw, url=url), self.previous)

    def test_invalid_connection_inputs_rejected(self):
        base = dict(self.previous)
        for patch in [
            {"url": "file:///etc/passwd"},
            {"url": "https://user:pass@example.invalid"},
            {"url": "https://example.invalid/?token=x"},
            {"url": "https://example.invalid/#x"},
            {"url": "https://example.invalid:bad"},
            {"token": "bad\r\nheader"},
            {"verify": "false"},
            {"timeout": True},
            {"timeout": 31},
        ]:
            with self.subTest(fields=list(patch)), self.assertRaises(ValueError):
                console.validate_connection(dict(base, **patch), self.previous)

    def test_source_identity_preserves_case_sensitive_url_paths(self):
        self.assertNotEqual(
            console.source_id("https://example.invalid/TenantA"),
            console.source_id("https://example.invalid/tenanta"),
        )
        self.assertEqual(
            console.source_id("https://EXAMPLE.invalid/TenantA/"),
            console.source_id("https://example.invalid/TenantA"),
        )

    def test_redirects_are_never_followed_with_api_credentials(self):
        calls = []

        class Redirect(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_GET(self):
                calls.append(self.path)
                self.send_response(302)
                self.send_header("Location", "/redirect-target")
                self.end_headers()

        server = ThreadingHTTPServer(("127.0.0.1", 0), Redirect)
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        try:
            cfg = dict(self.previous, url=f"http://127.0.0.1:{server.server_port}", timeout=2)
            with self.assertRaises(engine.ApiError):
                engine.Client(cfg).get("/api/endpoints")
            self.assertEqual(calls, ["/api/endpoints"])
        finally:
            server.shutdown()
            server.server_close()
            worker.join()


class HttpIsolationTests(TemporaryStoreTest):
    PASSWORD = "Synthetic-Admin-Password-Only"

    def setUp(self):
        super().setUp()
        self.store.set_setting("admin_password", console.password_hash(self.PASSWORD))
        self.manager = FakeManager(self.store)
        self.saved = self.store.save_dashboard(validate_dashboard(definition()))
        self.capability = self.store.share(self.saved["id"])
        # The fixture isolates public-share routing from HTML rendering.
        self.web = Path(self.temporary.name) / "fake-web"
        self.web.mkdir()
        (self.web / "shared.html").write_text(
            "<!doctype html><title>Synthetic viewer</title>", encoding="utf-8"
        )
        self.web_patch = mock.patch.object(console, "WEB", self.web)
        self.web_patch.start()
        self.server = console.create_server("127.0.0.1", 0, self.manager, local_admin=False)
        self.worker = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.worker.start()
        self.url = f"http://127.0.0.1:{self.server.server_port}"
        self.client = requests.Session()
        self.client.trust_env = False

    def tearDown(self):
        self.client.close()
        self.server.shutdown()
        self.server.server_close()
        self.worker.join()
        self.web_patch.stop()
        self.manager = None
        super().tearDown()

    def request(self, method, path, **kwargs):
        return self.client.request(method, self.url + path, timeout=3, **kwargs)

    def login(self):
        response = self.request("POST", "/api/login", json={"password": self.PASSWORD})
        self.assertEqual(response.status_code, 200)
        self.csrf = response.json()["csrf"]
        self.assertIn("HttpOnly", response.headers["Set-Cookie"])
        self.assertIn("SameSite=Strict", response.headers["Set-Cookie"])
        return {"X-Console-CSRF": self.csrf}

    def test_remote_session_cannot_auto_promote_or_read_admin_resources(self):
        self.assertFalse(self.request("GET", "/api/session").json()["admin"])
        for path in (
            "/api/snapshot",
            "/api/settings",
            "/api/catalog",
            "/api/dashboards",
            f"/api/dashboards/{self.saved['id']}",
            "/api/environments/3/events",
            "/api/environments/3/containers/" + "a" * 64 + "/inspect",
            "/api/environments/3/containers/" + "a" * 64 + "/logs",
        ):
            with self.subTest(path=path):
                r = self.request("GET", path, headers={"X-Forwarded-For": "127.0.0.1"})
                self.assertEqual(r.status_code, 401)
        self.manager.collector.docker.assert_not_called()

    def test_public_share_never_grants_editor_or_settings_access(self):
        r = self.request("GET", f"/api/public/dashboards/{self.capability}")
        self.assertEqual(r.status_code, 200)
        self.assertNotIn("PRIVATE_", r.text)
        self.assertNotIn(self.capability, r.text)
        self.assertEqual(
            self.request("POST", "/api/dashboards", json=definition()).status_code, 401
        )
        self.assertEqual(self.request("PUT", "/api/settings", json={}).status_code, 401)
        self.assertEqual(self.request("GET", "/api/snapshot").status_code, 401)

    def test_revoked_public_share_immediately_returns_not_found(self):
        path = f"/api/public/dashboards/{self.capability}"
        self.assertEqual(self.request("GET", path).status_code, 200)
        self.store.share(self.saved["id"], "disable")
        self.assertEqual(self.request("GET", path).status_code, 404)

    def test_csrf_required_for_each_mutation(self):
        headers = self.login()
        for method, path, body in [
            ("POST", "/api/dashboards", definition()),
            ("PUT", f"/api/dashboards/{self.saved['id']}", definition(revision=1)),
            ("DELETE", f"/api/dashboards/{self.saved['id']}", {"revision": 1}),
        ]:
            with self.subTest(method=method):
                self.assertEqual(self.request(method, path, json=body).status_code, 403)
                self.assertEqual(
                    self.request(
                        method, path, json=body, headers={"X-Console-CSRF": "wrong"}
                    ).status_code,
                    403,
                )
        self.assertEqual(
            self.request("POST", "/api/dashboards", json=definition(), headers=headers).status_code,
            201,
        )

    def test_authenticated_crud_conflict_share_and_logout(self):
        headers = self.login()
        create = self.request("POST", "/api/dashboards", json=definition(), headers=headers)
        saved = create.json()
        path = "/api/dashboards/" + saved["id"]
        update = definition(name="Changed through API", revision=saved["revision"])
        self.assertEqual(self.request("PUT", path, json=update, headers=headers).status_code, 200)
        self.assertEqual(self.request("PUT", path, json=update, headers=headers).status_code, 409)
        shared = self.request("POST", path + "/share", json={"action": "enable"}, headers=headers)
        self.assertEqual(shared.status_code, 200)
        self.assertTrue(shared.json()["path"].startswith("/d/"))
        self.assertEqual(
            self.request("DELETE", path, json={"revision": 2}, headers=headers).status_code, 200
        )
        self.assertEqual(
            self.request("POST", "/api/logout", json={}, headers=headers).status_code, 200
        )
        self.assertEqual(self.request("GET", "/api/snapshot").status_code, 401)

    def test_cross_origin_and_host_headers_rejected(self):
        headers = self.login()
        for extra in (
            {"Origin": "https://attacker.invalid"},
            {"Sec-Fetch-Site": "cross-site"},
            {"Host": "attacker.invalid"},
        ):
            with self.subTest(headers=list(extra)):
                self.assertEqual(
                    self.request(
                        "POST", "/api/dashboards", json=definition(), headers=dict(headers, **extra)
                    ).status_code,
                    403,
                )

    def test_shared_link_allows_cross_site_top_level_navigation(self):
        r = self.request(
            "GET",
            f"/d/{self.capability}",
            headers={
                "Sec-Fetch-Site": "cross-site",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Dest": "document",
            },
        )
        self.assertEqual(r.status_code, 200)

    def test_private_files_are_never_served(self):
        for path in ("/.env", "/engine.py", "/persistence.py", "/data/console.sqlite3", "/../.env"):
            with self.subTest(path=path):
                self.assertEqual(self.request("GET", path).status_code, 404)

    def test_login_bruteforce_limit(self):
        for _ in range(5):
            self.assertEqual(
                self.request("POST", "/api/login", json={"password": "incorrect"}).status_code, 401
            )
        self.assertEqual(
            self.request("POST", "/api/login", json={"password": "incorrect"}).status_code, 429
        )

    def test_json_type_and_nonfinite_payloads_rejected(self):
        headers = self.login()
        self.assertEqual(
            self.request("POST", "/api/dashboards", data="{}", headers=headers).status_code, 400
        )
        self.assertEqual(
            self.request(
                "POST",
                "/api/dashboards",
                data='{"name":NaN}',
                headers=dict(headers, **{"Content-Type": "application/json"}),
            ).status_code,
            400,
        )


if __name__ == "__main__":
    unittest.main()
