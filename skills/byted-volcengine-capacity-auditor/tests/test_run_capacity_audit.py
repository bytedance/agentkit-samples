import importlib.util
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "run_capacity_audit.py"
SPEC = importlib.util.spec_from_file_location("run_capacity_audit", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


class TopologyScopeTests(unittest.TestCase):
    def test_build_topology_scope_collects_supported_chain_resources(self) -> None:
        topology = {
            "nodes": [
                {"id": "alb-1", "type": "alb", "name": "alb-main"},
                {"id": "clb-1", "type": "clb", "name": "clb-main"},
                {"id": "ecs-1", "type": "ecs", "name": "ecs-app"},
                {"id": "rds-1", "type": "rds_mysql", "name": "rds-main"},
                {"id": "sg-1", "type": "security_group", "name": "sg-1"},
            ],
            "chains": {
                "alb-1": {
                    "path": [
                        {"id": "alb-1", "type": "alb"},
                    ],
                    "contexts": {},
                },
                "clb-1": {
                    "ecs-1": {
                        "path": [
                            {"id": "clb-1", "type": "clb"},
                            {"id": "ecs-1", "type": "ecs"},
                        ],
                        "contexts": {
                            "ecs-1": {
                                "database": ["rds-1"],
                                "security_group": ["sg-1"],
                            }
                        },
                    }
                }
            },
        }

        scope = MODULE.build_topology_scope(topology, Path("/tmp/topology.json"))

        self.assertTrue(scope["enabled"])
        self.assertEqual(scope["resource_ids"]["alb"], ["alb-1"])
        self.assertEqual(scope["resource_ids"]["clb"], ["clb-1"])
        self.assertEqual(scope["resource_ids"]["ecs"], ["ecs-1"])
        self.assertEqual(scope["resource_ids"]["rds_mysql"], ["rds-1"])
        self.assertEqual(scope["resource_counts"]["alb"], 1)
        self.assertEqual(scope["resource_counts"]["clb"], 1)
        self.assertEqual(scope["resource_counts"]["ecs"], 1)
        self.assertEqual(scope["resource_counts"]["rds_mysql"], 1)
        self.assertEqual(scope["paths"], ["alb:alb-main", "clb:clb-main -> ecs:ecs-app"])

    def test_build_topology_scope_supports_single_route_root(self) -> None:
        topology = {
            "nodes": [
                {"id": "rds-1", "type": "rds_mysql", "name": "rds-main"},
            ],
            "chains": {
                "rds-1": {
                    "path": [
                        {"id": "rds-1", "type": "rds_mysql"},
                    ],
                    "contexts": {},
                }
            },
        }

        scope = MODULE.build_topology_scope(topology, Path("/tmp/topology.json"))

        self.assertEqual(scope["resource_ids"]["rds_mysql"], ["rds-1"])
        self.assertEqual(scope["paths"], ["rds_mysql:rds-main"])


class AlbSupportTests(unittest.TestCase):
    def test_safe_fetch_metric_summary_candidates_passes_extra_dimensions(self) -> None:
        captured = {}

        def fake_safe_fetch_metric_summary(**kwargs):
            captured.update(kwargs)
            return {"count": 1, "avg": 1.0, "max": 1.0, "p95": 1.0}

        original = MODULE.safe_fetch_metric_summary
        MODULE.safe_fetch_metric_summary = fake_safe_fetch_metric_summary
        try:
            summary = MODULE.safe_fetch_metric_summary_candidates(
                [{"namespace": "VCM_ALB", "sub_namespace": "listener", "metric_name": "listener_qps"}],
                "alb-1",
                "1h",
                1,
                2,
                extra_dimensions=[{"name": "ListenerID", "value": "lsn-1"}],
            )
        finally:
            MODULE.safe_fetch_metric_summary = original

        self.assertEqual(captured["resource_id"], "alb-1")
        self.assertEqual(captured["extra_dimensions"], [{"name": "ListenerID", "value": "lsn-1"}])
        self.assertEqual(summary["p95"], 1.0)

    def test_alb_recommendation_marks_anomaly_when_errors_exist(self) -> None:
        healthy = {"count": 1, "p95": 10}
        no_error = {"count": 1, "p95": 0}
        with_error = {"count": 1, "p95": 1}

        self.assertEqual(
            MODULE.alb_recommendation(healthy, healthy, healthy, no_error, with_error),
            "入口层存在异常信号，建议优先排查",
        )


class ClbSupportTests(unittest.TestCase):
    def test_fetch_clb_listeners_clamps_page_size(self) -> None:
        captured = {}

        class FakeResponse:
            def to_dict(self):
                return {"listeners": []}

        class FakeApi:
            def describe_listeners(self, request):
                captured["request"] = request
                return FakeResponse()

        original_api = MODULE.CLBApi
        original_request = MODULE.DescribeClbListenersRequest
        MODULE.CLBApi = lambda: FakeApi()
        MODULE.DescribeClbListenersRequest = lambda **kwargs: kwargs
        try:
            MODULE.fetch_clb_listeners(limit=200, load_balancer_id="clb-1")
        finally:
            MODULE.CLBApi = original_api
            MODULE.DescribeClbListenersRequest = original_request

        self.assertEqual(captured["request"]["page_size"], 100)
        self.assertEqual(captured["request"]["page_number"], 1)
        self.assertEqual(captured["request"]["load_balancer_id"], "clb-1")

    def test_build_clb_report_fetches_metrics_before_billing_fallback(self) -> None:
        metric_calls = []

        def fake_fetch_clb_listeners(*args, **kwargs):
            return [{"listener_id": "lsn-1", "listener_name": "http", "protocol": "HTTP", "port": 80}]

        def fake_safe_fetch_metric_summary_candidates(
            candidates, resource_id, period, start_time, end_time, extra_dimensions=None
        ):
            metric_calls.append(candidates[0]["metric_name"])
            return {"count": 1, "avg": 8.0, "max": 10.0, "p95": 10.0}

        original_fetch_clb_listeners = MODULE.fetch_clb_listeners
        original_safe_fetch_metric_summary_candidates = MODULE.safe_fetch_metric_summary_candidates
        MODULE.fetch_clb_listeners = fake_fetch_clb_listeners
        MODULE.safe_fetch_metric_summary_candidates = fake_safe_fetch_metric_summary_candidates
        try:
            report = MODULE.build_clb_report(
                [
                    {
                        "load_balancer_id": "clb-1",
                        "load_balancer_name": "clb-main",
                        "project_name": "mysite",
                        "load_balancer_spec": "small_1",
                        "status": "active",
                        "type": "public",
                        "load_balancer_billing_type": "traffic",
                    }
                ],
                now=100,
            )
        finally:
            MODULE.fetch_clb_listeners = original_fetch_clb_listeners
            MODULE.safe_fetch_metric_summary_candidates = original_safe_fetch_metric_summary_candidates

        item = report["instances"][0]
        self.assertEqual(
            set(metric_calls),
            {
                "listener_qps",
                "listener_max_conn",
                "listener_new_conn",
                "listener_in_bytes",
                "listener_out_bytes",
            },
        )
        self.assertEqual(item["listener_count"], 1)
        self.assertEqual(item["qps_30d"]["p95"], 10.0)
        self.assertEqual(item["recommendation"], "已获取入口层监控摘要，后续需结合实例规格上限做使用率换算")
        self.assertEqual(item["data_gaps"], [])
        self.assertEqual(report["data_gaps"], [])

    def test_build_clb_report_does_not_treat_tcp_listener_qps_as_gap(self) -> None:
        metric_calls = []

        def fake_fetch_clb_listeners(*args, **kwargs):
            return [{"listener_id": "lsn-1", "listener_name": "tcp", "protocol": "TCP", "port": 80}]

        def fake_safe_fetch_metric_summary_candidates(
            candidates, resource_id, period, start_time, end_time, extra_dimensions=None
        ):
            metric_calls.append(candidates[0]["metric_name"])
            return {"count": 1, "avg": 6.0, "max": 9.0, "p95": 9.0}

        original_fetch_clb_listeners = MODULE.fetch_clb_listeners
        original_safe_fetch_metric_summary_candidates = MODULE.safe_fetch_metric_summary_candidates
        MODULE.fetch_clb_listeners = fake_fetch_clb_listeners
        MODULE.safe_fetch_metric_summary_candidates = fake_safe_fetch_metric_summary_candidates
        try:
            report = MODULE.build_clb_report(
                [
                    {
                        "load_balancer_id": "clb-2",
                        "load_balancer_name": "clb-tcp",
                        "project_name": "mysite",
                        "load_balancer_spec": "small_1",
                        "status": "active",
                        "type": "private",
                        "load_balancer_billing_type": "postpaid",
                    }
                ],
                now=100,
            )
        finally:
            MODULE.fetch_clb_listeners = original_fetch_clb_listeners
            MODULE.safe_fetch_metric_summary_candidates = original_safe_fetch_metric_summary_candidates

        item = report["instances"][0]
        self.assertEqual(
            set(metric_calls),
            {
                "listener_max_conn",
                "listener_new_conn",
                "listener_in_bytes",
                "listener_out_bytes",
            },
        )
        self.assertFalse(item["qps_expected"])
        self.assertEqual(item["qps_30d"]["count"], 0)
        self.assertEqual(item["data_gaps"], [])
        self.assertIn("七层 QPS 默认不纳入判断", item["protocol_note"])


if __name__ == "__main__":
    unittest.main()
