import json
import subprocess
import tempfile
import unittest
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
BUILD_SCRIPT = SCRIPT_DIR / "build_topology_from_account_assets.py"
SAVE_SCRIPT = SCRIPT_DIR / "save_topology.py"
RENDER_SCRIPT = SCRIPT_DIR / "render_topology_graph.py"


def run_python_script(script_path: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["python3", str(script_path), *args],
        check=True,
        capture_output=True,
        text=True,
    )


def write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def ingress_snapshot() -> dict:
    return {
        "version": "0.1",
        "region": "cn-beijing",
        "project_names": ["demo"],
        "assets": {
            "ecs": {
                "instances": [
                    {
                        "instance_id": "i-demo-001",
                        "instance_name": "demo-ecs",
                        "project_name": "demo",
                        "vpc_id": "vpc-demo",
                        "volumes": [{"volume_id": "vol-demo-001"}],
                        "network_interfaces": [
                            {
                                "subnet_id": "subnet-demo-a",
                                "vpc_id": "vpc-demo",
                                "security_group_ids": ["sg-demo"],
                            }
                        ],
                    }
                ]
            },
            "eip": {
                "items": [
                    {
                        "allocation_id": "eipalloc-demo",
                        "eip_address": "1.1.1.1",
                        "instance_id": "clb-demo",
                        "instance_type": "CLB",
                    }
                ]
            },
            "clb_load_balancers": {
                "items": [
                    {
                        "load_balancer_id": "clb-demo",
                        "load_balancer_name": "demo-clb",
                        "project_name": "demo",
                        "vpc_id": "vpc-demo",
                        "subnet_id": "subnet-demo-a",
                    }
                ]
            },
            "clb_listeners": {
                "items": [
                    {
                        "listener_id": "listener-demo",
                        "listener_name": "tcp-80",
                        "load_balancer_id": "clb-demo",
                    }
                ]
            },
            "clb_server_groups": {
                "items": [
                    {
                        "server_group_id": "sgp-demo",
                        "server_group_name": "demo-group",
                        "load_balancer_id": "clb-demo",
                    }
                ]
            },
            "clb_server_group_attributes": {
                "sgp-demo": {
                    "load_balancer_id": "clb-demo",
                    "servers": [{"instance_id": "i-demo-001"}],
                }
            },
            "alb_load_balancers": {"items": []},
            "alb_listeners": {"items": []},
            "alb_server_groups": {"items": []},
            "alb_server_group_backends": {},
            "nat_gateways": {"items": []},
            "dnat_entries": {"items": []},
            "rds_mysql_instances": {"items": []},
            "redis_instances": {"items": []},
        },
        "errors": [],
    }


def managed_db_snapshot() -> dict:
    return {
        "version": "0.1",
        "region": "cn-beijing",
        "project_names": ["mysite"],
        "assets": {
            "ecs": {"instances": []},
            "eip": {"items": []},
            "clb_load_balancers": {"items": []},
            "clb_listeners": {"items": []},
            "clb_server_groups": {"items": []},
            "clb_server_group_attributes": {},
            "alb_load_balancers": {"items": []},
            "alb_listeners": {"items": []},
            "alb_server_groups": {"items": []},
            "alb_server_group_backends": {},
            "nat_gateways": {"items": []},
            "dnat_entries": {"items": []},
            "rds_mysql_instances": {
                "items": [
                    {
                        "instance_id": "mysql-demo",
                        "instance_name": "mysql-demo-name",
                        "project_name": "mysite",
                        "vpc_id": "vpc-demo",
                        "subnet_id": "subnet-db-a",
                        "zone_ids": ["cn-beijing-a"],
                    }
                ]
            },
            "redis_instances": {
                "items": [
                    {
                        "instance_id": "redis-demo",
                        "instance_name": "redis-demo-name",
                        "project_name": "mysite",
                        "vpc_id": "vpc-demo",
                        "private_address": "redis-demo.redis.ivolces.com",
                        "private_port": "6379",
                        "zone_ids": ["cn-beijing-a"],
                    }
                ]
            },
        },
        "errors": [],
    }


def mixed_snapshot() -> dict:
    snapshot = ingress_snapshot()
    snapshot["assets"]["rds_mysql_instances"] = managed_db_snapshot()["assets"][
        "rds_mysql_instances"
    ]
    snapshot["assets"]["redis_instances"] = managed_db_snapshot()["assets"][
        "redis_instances"
    ]
    return snapshot


class TopologyBuilderE2ETest(unittest.TestCase):
    maxDiff = None

    def build_save_and_render(
        self, snapshot: dict, business_key: str
    ) -> tuple[dict, dict, str]:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            assets_file = tmp_path / "account_assets_snapshot.json"
            topology_file = tmp_path / "topology.json"
            render_dir = tmp_path / "rendered"
            root_dir = tmp_path / "business_topologies"
            write_json(assets_file, snapshot)

            run_python_script(
                BUILD_SCRIPT,
                "--assets-file",
                str(assets_file),
                "--region",
                "cn-beijing",
                "--output-file",
                str(topology_file),
            )
            run_python_script(
                SAVE_SCRIPT,
                "--business",
                business_key,
                "--topology-file",
                str(topology_file),
                "--root",
                str(root_dir),
                "--skip-render-graph",
            )
            render_result = run_python_script(
                RENDER_SCRIPT,
                "--topology-file",
                str(topology_file),
                "--output-dir",
                str(render_dir),
                "--context-as-attributes",
                "--skip-auto-install-graphviz",
            )

            topology = json.loads(topology_file.read_text(encoding="utf-8"))
            render_data = json.loads(render_result.stdout)
            saved_dir = root_dir / business_key
            self.assertTrue((saved_dir / "topology.json").exists())
            self.assertTrue((saved_dir / "topology.md").exists())
            self.assertTrue(Path(render_data["topology_dot"]).exists())
            if render_data.get("graphviz_available"):
                self.assertTrue(Path(render_data["topology_svg"]).exists())
                self.assertTrue(Path(render_data["topology_png"]).exists())
            md_content = (saved_dir / "topology.md").read_text(encoding="utf-8")
            return topology, render_data, md_content

    def test_ingress_topology_build_and_render_do_not_fail(self) -> None:
        topology, _, md_content = self.build_save_and_render(
            ingress_snapshot(), "ingress-demo"
        )
        node_types = {node["type"] for node in topology["nodes"]}
        self.assertIn("clb", node_types)
        self.assertIn("ecs", node_types)
        self.assertIn("listener", node_types)
        self.assertIn("server_group", node_types)
        self.assertIn("CLB:clb-demo", md_content)
        self.assertIn("ECS:i-demo-001", md_content)

    def test_managed_db_topology_build_and_render_do_not_fail(self) -> None:
        topology, _, md_content = self.build_save_and_render(
            managed_db_snapshot(), "managed-db-demo"
        )
        node_types = {node["type"] for node in topology["nodes"]}
        self.assertIn("rds_mysql", node_types)
        self.assertIn("redis", node_types)
        self.assertIn("project", node_types)

        chains = topology["chains"]
        self.assertIn("mysql-demo", chains)
        self.assertIn("redis-demo", chains)
        self.assertEqual(
            chains["mysql-demo"]["contexts"]["mysql-demo"]["project"],
            ["project:mysite"],
        )
        self.assertIn("vpc", chains["redis-demo"]["contexts"]["redis-demo"])

        self.assertIn("RDS MySQL:mysql-demo", md_content)
        self.assertIn("Redis:redis-demo", md_content)
        self.assertIn("项目:mysite", md_content)

    def test_mixed_topology_build_and_render_do_not_fail(self) -> None:
        topology, render_data, _ = self.build_save_and_render(
            mixed_snapshot(), "mixed-demo"
        )
        node_types = {node["type"] for node in topology["nodes"]}
        self.assertTrue(
            {"clb", "ecs", "rds_mysql", "redis", "project"}.issubset(node_types)
        )

        terminal_nodes = set()
        for chain in topology["chains"].values():
            routes = (
                [chain]
                if isinstance(chain.get("path"), list)
                else [route for route in chain.values() if isinstance(route, dict)]
            )
            for route in routes:
                path = route.get("path") or []
                if path:
                    terminal_nodes.add((path[-1]["type"], path[-1]["id"]))

        self.assertIn(("rds_mysql", "mysql-demo"), terminal_nodes)
        self.assertIn(("redis", "redis-demo"), terminal_nodes)
        self.assertIn("topology_dot", render_data)


if __name__ == "__main__":
    unittest.main()
