"""Synthetic regression checks; no requests to the user's Portainer instance."""

import json
import tempfile
import threading
import unittest

import requests

import portainer_console as console
from engine import decode_logs, normalize_df, safe_inspect, stats_metrics, storage_summary
from persistence import Store


class MetricsTests(unittest.TestCase):
    def test_cpu_uses_logical_core_semantics(self):
        raw = {
            "cpu_stats": {
                "online_cpus": 4,
                "system_cpu_usage": 5000,
                "cpu_usage": {"total_usage": 500},
            },
            "precpu_stats": {"system_cpu_usage": 1000, "cpu_usage": {"total_usage": 100}},
        }
        self.assertEqual(stats_metrics(raw)["cpu_percent"], 40)

    def test_one_shot_uses_previous_system_counter(self):
        previous = {"cpu_total": 100, "system_cpu_total": 1000, "sample_at": "2026-01-01T00:00:00Z"}
        raw = {
            "read": "2026-01-01T00:00:05Z",
            "cpu_stats": {
                "online_cpus": 2,
                "system_cpu_usage": 2000,
                "cpu_usage": {"total_usage": 600},
            },
        }
        self.assertEqual(stats_metrics(raw, previous, 900)["cpu_percent"], 100)

    def test_initial_cpu_and_rates_unknown(self):
        result = stats_metrics({"networks": {"eth0": {"rx_bytes": 100, "tx_bytes": 100}}})
        self.assertIsNone(result["cpu_percent"])
        self.assertIsNone(result["rx_rate"])

    def test_network_uses_engine_timestamps(self):
        previous = {"rx_bytes": 100, "tx_bytes": 200, "sample_at": "2026-01-01T00:00:00Z"}
        raw = {
            "read": "2026-01-01T00:00:02Z",
            "networks": {"eth0": {"rx_bytes": 300, "tx_bytes": 300}},
        }
        self.assertEqual(stats_metrics(raw, previous, 100)["rx_rate"], 100)

    def test_counter_reset_never_negative(self):
        raw = {"networks": {"eth0": {"rx_bytes": 0, "tx_bytes": 0}}}
        result = stats_metrics(raw, {"rx_bytes": 500, "tx_bytes": 500}, 2)
        self.assertIsNone(result["rx_rate"])

    def test_cgroup_memory_working_set(self):
        for counter in ("inactive_file", "total_inactive_file"):
            raw = {"memory_stats": {"usage": 1000, "limit": 2000, "stats": {counter: 400}}}
            self.assertEqual(stats_metrics(raw)["memory_bytes"], 600)

    def test_memory_without_usage_is_unknown(self):
        result = stats_metrics({"memory_stats": {"stats": {"inactive_file": 0}}})
        self.assertIsNone(result["memory_bytes"])
        self.assertIsNone(result["cache_bytes"])

    def test_inconsistent_cache_preserves_usage(self):
        result = stats_metrics({"memory_stats": {"usage": 100, "stats": {"inactive_file": 150}}})
        self.assertEqual(result["memory_bytes"], 100)

    def test_absent_cache_preserves_usage(self):
        self.assertEqual(stats_metrics({"memory_stats": {"usage": 100}})["memory_bytes"], 100)


class StorageTests(unittest.TestCase):
    def test_shared_cache_not_counted_twice(self):
        result = storage_summary(
            {
                "LayersSize": 100,
                "BuildCache": [
                    {"Size": 100, "Shared": True},
                    {"Size": 20, "Shared": False, "InUse": False},
                ],
            }
        )
        self.assertEqual(result["cache_bytes"], 20)
        self.assertEqual(result["cache_reclaimable_bytes"], 20)

    def test_omitted_zero_writable_size(self):
        self.assertEqual(
            storage_summary({"Containers": [{"Id": "a"}, {"Id": "b", "SizeRw": 20}]})[
                "writable_bytes"
            ],
            20,
        )

    def test_unknown_volume_is_not_zero(self):
        result = storage_summary(
            {"Volumes": [{"UsageData": {"Size": 200}}, {"UsageData": {"Size": -1}}]}
        )
        self.assertIsNone(result["volumes_bytes"])
        self.assertEqual(result["volume_known_bytes"], 200)
        self.assertEqual(result["volume_unknown_count"], 1)

    def test_modern_storage_categories(self):
        df = {
            "ImageUsage": {"TotalSize": 100, "Items": [{"Id": "a"}]},
            "ContainerUsage": {"TotalSize": 20},
            "VolumeUsage": {"TotalSize": 30},
            "BuildCacheUsage": {"TotalSize": 40, "Reclaimable": 10},
        }
        result = storage_summary(df)
        self.assertEqual(result["layers_bytes"], 100)
        self.assertEqual(result["writable_bytes"], 20)
        self.assertEqual(result["volumes_bytes"], 30)
        self.assertEqual(result["cache_bytes"], 40)
        self.assertEqual(normalize_df(df)["Images"], [{"Id": "a"}])

    def test_missing_storage_is_unknown(self):
        self.assertFalse(storage_summary(None)["available"])


class PrivacyTests(unittest.TestCase):
    def test_inspect_drops_health_output_and_environment_values(self):
        raw = {
            "Config": {
                "Env": ["PUBLIC_URL=https://example.test", "PASSWORD=SYNTHETIC_SECRET"],
                "Cmd": ["SYNTHETIC_SECRET"],
            },
            "State": {"Health": {"Status": "healthy", "Log": [{"Output": "SYNTHETIC_SECRET"}]}},
        }
        result = safe_inspect(raw)
        self.assertNotIn("SYNTHETIC_SECRET", json.dumps(result))
        self.assertEqual(result["State"]["Health"]["Status"], "healthy")
        self.assertEqual(result["Config"]["Env"][0], "PUBLIC_URL=[hidden]")

    def test_log_secret_formats(self):
        for line in [
            '{"token":"SYNTHETIC_SECRET"}',
            "password=SYNTHETIC_SECRET",
            "Authorization: Bearer SYNTHETIC_SECRET",
            "https://user:SYNTHETIC_SECRET@example.test/",
        ]:
            self.assertNotIn("SYNTHETIC_SECRET", decode_logs(line.encode()))

    def test_docker_log_multiplexing(self):
        def frame(stream, payload):
            return bytes([stream, 0, 0, 0]) + len(payload).to_bytes(4, "big") + payload

        raw = frame(1, b"hello\n") + frame(2, b"error\n")
        self.assertEqual(decode_logs(raw), "hello\nerror\n")

    def test_plain_tty_logs(self):
        self.assertEqual(decode_logs(b"normal terminal output\n"), "normal terminal output\n")


class FakeManager:
    standalone = True

    def __init__(self, store):
        self.store = store
        self.lock = threading.RLock()
        self.collector = self
        self.generation = "synthetic-generation"

    def snapshot(self):
        return {
            "status": "live",
            "sequence": 1,
            "updated_at": "2026-01-01T00:00:00Z",
            "environments": [],
        }


class HttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory()
        cls.store = Store(cls.temporary.name)
        cls.store.set_setting(
            "admin_password", console.password_hash("Synthetic-HTTP-Test-Password")
        )
        cls.server = console.create_server(
            "127.0.0.1", 0, FakeManager(cls.store), local_admin=False
        )
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.url = f"http://127.0.0.1:{cls.server.server_port}"
        cls.session = requests.Session()
        cls.session.trust_env = False
        response = cls.session.post(
            cls.url + "/api/login", json={"password": "Synthetic-HTTP-Test-Password"}, timeout=3
        )
        if response.status_code != 200:
            raise AssertionError("Synthetic HTTP test login failed")

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()
        cls.session.close()
        cls.temporary.cleanup()

    def test_only_allowlisted_files_are_served(self):
        for path in (
            "/.env",
            "/portainer_console.py",
            "/engine.py",
            "/../.env",
            "/%2e%2e/.env",
            "/data/",
        ):
            self.assertEqual(self.session.get(self.url + path, timeout=2).status_code, 404)

    def test_web_assets_and_headers(self):
        for path in ("/", "/app.js", "/views.js", "/controller.js", "/styles.css"):
            response = self.session.get(self.url + path, timeout=2)
            self.assertEqual(response.status_code, 200)
            self.assertIn("frame-ancestors 'none'", response.headers["Content-Security-Policy"])

    def test_cross_site_requests_rejected(self):
        for headers in (
            {"Host": "attacker.test"},
            {"Origin": "https://attacker.test"},
            {"Sec-Fetch-Site": "cross-site"},
        ):
            self.assertEqual(
                self.session.get(
                    self.url + "/api/snapshot", headers=headers, timeout=2
                ).status_code,
                403,
            )

    def test_unknown_container_cannot_proxy(self):
        response = self.session.get(
            self.url + "/api/environments/999/containers/" + "a" * 64 + "/inspect", timeout=2
        )
        self.assertEqual(response.status_code, 404)


if __name__ == "__main__":
    unittest.main()
