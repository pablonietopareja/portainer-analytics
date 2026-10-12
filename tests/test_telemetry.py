import unittest

from telemetry import EXTRA_METRICS, extend_stats, flatten_numeric_stats


class TelemetryTests(unittest.TestCase):
    def test_missing_not_zero(self):
        metrics = extend_stats({})
        self.assertTrue(all(metrics[k] is None for k in EXTRA_METRICS))
        self.assertEqual(metrics["raw_metrics"], {})

    def test_network_counters_rates_and_reset(self):
        raw = {
            "networks": {
                "eth0": {"rx_packets": 14, "rx_dropped": 0},
                "eth1": {"rx_packets": 6, "rx_dropped": 2},
            }
        }
        measured = extend_stats(raw, {"rx_packets": 10, "rx_dropped": 5}, 2)
        self.assertEqual(measured["rx_packets"], 20)
        self.assertEqual(measured["rx_packets_rate"], 5)
        self.assertIsNone(measured["rx_dropped_rate"])
        self.assertIsNone(measured["tx_packets"])

    def test_empty_or_invalid_io_not_fabricated_zero(self):
        self.assertIsNone(
            extend_stats({"blkio_stats": {"io_service_bytes_recursive": []}})["block_read_bytes"]
        )
        self.assertIsNone(
            extend_stats(
                {"blkio_stats": {"io_service_bytes_recursive": [{"op": "Read", "value": -1}]}}
            )["block_read_bytes"]
        )

    def test_io_totals_rates_operations(self):
        raw = {
            "blkio_stats": {
                "io_service_bytes_recursive": [
                    {"op": "Read", "value": 120},
                    {"op": "read", "value": 80},
                    {"op": "Write", "value": 1000},
                ],
                "io_serviced_recursive": [{"op": "Read", "value": 8}],
            }
        }
        actual = extend_stats(raw, {"block_read_bytes": 100, "block_read_ops": 4}, 2)
        self.assertEqual(actual["block_read_bytes"], 200)
        self.assertEqual(actual["block_read_rate"], 50)
        self.assertEqual(actual["block_read_ops_rate"], 2)
        self.assertIsNone(actual["block_write_ops"])

    def test_cgroup_two_memory_and_limits(self):
        raw = {
            "memory_stats": {
                "usage": 200,
                "limit": 1000,
                "stats": {"anon": 120, "file": 60, "pgfault": 40},
            },
            "pids_stats": {"current": 5, "limit": 10},
        }
        actual = extend_stats(raw, {"memory_page_faults": 20}, 5, {"memory_bytes": 140})
        self.assertAlmostEqual(actual["memory_limit_percent"], 14)
        self.assertEqual(actual["memory_rss_bytes"], 120)
        self.assertEqual(actual["memory_file_bytes"], 60)
        self.assertEqual(actual["memory_page_fault_rate"], 4)
        self.assertEqual(actual["pids_limit_percent"], 50)
        self.assertIsNone(actual["memory_peak_bytes"])
        self.assertIsNone(actual["memory_swap_bytes"])

    def test_cgroup_one_total_counters_preferred(self):
        raw = {
            "memory_stats": {
                "stats": {
                    "rss": 20,
                    "total_rss": 0,
                    "cache": 10,
                    "total_cache": 40,
                    "total_swap": 8,
                }
            },
            "pids_stats": {"current": 3, "limit": 0},
        }
        actual = extend_stats(raw)
        self.assertEqual(actual["memory_rss_bytes"], 0)
        self.assertEqual(actual["memory_file_bytes"], 40)
        self.assertEqual(actual["memory_swap_bytes"], 8)
        self.assertIsNone(actual["pids_limit"])

    def test_cpu_times_throttle_and_percentage(self):
        raw = {
            "cpu_stats": {
                "cpu_usage": {
                    "total_usage": 4000000000,
                    "usage_in_usermode": 3000000000,
                    "usage_in_kernelmode": 1000000000,
                },
                "throttling_data": {
                    "periods": 20,
                    "throttled_periods": 6,
                    "throttled_time": 2000000000,
                },
            }
        }
        old = {
            "cpu_user_seconds": 1,
            "cpu_kernel_seconds": 0.5,
            "cpu_periods": 10,
            "cpu_throttled_periods": 4,
            "cpu_throttled_seconds": 1,
        }
        actual = extend_stats(raw, old, 2)
        self.assertEqual(actual["cpu_time_seconds"], 4)
        self.assertEqual(actual["cpu_user_percent"], 100)
        self.assertEqual(actual["cpu_kernel_percent"], 25)
        self.assertEqual(actual["cpu_throttled_percent"], 20)
        self.assertEqual(actual["cpu_throttled_time_rate"], 0.5)

    def test_windows_units_memory_and_io(self):
        raw = {
            "memory_stats": {"privateworkingset": 100, "commitbytes": 200},
            "cpu_stats": {"cpu_usage": {"total_usage": 20000000}},
            "storage_stats": {"read_size_bytes": 400, "read_count_normalized": 5},
            "networks": {"vEthernet": {"rx_errors": 0, "rx_packets": 7}},
        }
        actual = extend_stats(
            raw, {"cpu_total": 10000000, "block_read_bytes": 200}, 2, {"cpu_percent": 0.5}
        )
        self.assertEqual(actual["cpu_percent"], 50)
        self.assertEqual(actual["cpu_time_seconds"], 2)
        self.assertEqual(actual["memory_bytes"], 100)
        self.assertEqual(actual["memory_commit_bytes"], 200)
        self.assertEqual(actual["block_read_rate"], 100)
        self.assertIsNone(actual["memory_raw_bytes"])
        self.assertIsNone(actual["rx_errors"])
        self.assertIsNone(actual["pids"])

    def test_raw_telemetry_scoped_finite_bounded_and_no_strings(self):
        raw = {
            "memory_stats": {"stats": {"field" + str(i): i for i in range(700)}},
            "Config": {"Env": ["PASSWORD=secret"]},
        }
        actual = flatten_numeric_stats(raw)
        self.assertEqual(len(actual), 512)
        values = flatten_numeric_stats(
            {
                "cpu_stats": {"values": [False, float("inf"), float("nan"), "secret", 12, 10**400]},
                "networks": {"a.b/c~": {"rx_bytes": 3}},
            }
        )
        self.assertEqual(values, {"cpu_stats.values.4": 12, "networks.a~2b~1c~0.rx_bytes": 3})

    def test_rates_require_positive_sample_elapsed(self):
        for elapsed in (0, -1, None, False, float("nan")):
            actual = extend_stats(
                {"networks": {"eth0": {"rx_packets": 30}}}, {"rx_packets": 10}, elapsed
            )
            self.assertIsNone(actual["rx_packets_rate"])


if __name__ == "__main__":
    unittest.main()
