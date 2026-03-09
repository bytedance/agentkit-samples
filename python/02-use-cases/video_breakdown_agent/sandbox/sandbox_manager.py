"""
沙箱环境管理器
提供沙箱的启动、停止、重置、健康检查等功能
"""

import subprocess
import sys
import time
from pathlib import Path

import httpx


class SandboxManager:
    """沙箱环境管理器"""

    def __init__(self, sandbox_dir: str = None):
        self.sandbox_dir = Path(sandbox_dir) if sandbox_dir else Path(__file__).parent
        self.compose_file = self.sandbox_dir / "docker-compose.yml"
        self.env_file = self.sandbox_dir / ".env"
        self.api_url = "http://localhost:7115"

    def start(self, rebuild: bool = False):
        """启动沙箱环境"""
        print("启动沙箱环境...")

        # 检查 .env 文件
        if not self.env_file.exists():
            example_env = self.sandbox_dir / "sandbox.env.example"
            if example_env.exists():
                print(
                    "警告: 未找到 .env 文件，请复制 sandbox.env.example 为 .env 并填入配置"
                )
                print(f"  cp {example_env} {self.env_file}")
                return

        cmd = [
            "docker-compose",
            "-f",
            str(self.compose_file),
            "--env-file",
            str(self.env_file),
            "up",
            "-d",
        ]
        if rebuild:
            cmd.insert(-1, "--build")

        result = subprocess.run(
            cmd, capture_output=True, text=True, cwd=str(self.sandbox_dir)
        )
        if result.returncode != 0:
            print(f"沙箱启动失败: {result.stderr}")
            raise Exception(f"沙箱启动失败: {result.stderr}")

        print("等待服务就绪...")
        self.wait_for_health()
        print("沙箱环境已启动")
        print(f"  API 地址: {self.api_url}")
        print("  MySQL: localhost:3307")
        print("  Redis: localhost:6380")

    def stop(self):
        """停止沙箱环境（保留数据）"""
        print("停止沙箱环境...")
        cmd = [
            "docker-compose",
            "-f",
            str(self.compose_file),
            "down",
        ]
        subprocess.run(cmd, cwd=str(self.sandbox_dir))
        print("沙箱环境已停止")

    def reset(self):
        """重置沙箱环境（清除所有数据和卷）"""
        print("重置沙箱环境...")
        cmd = [
            "docker-compose",
            "-f",
            str(self.compose_file),
            "down",
            "-v",
        ]
        subprocess.run(cmd, cwd=str(self.sandbox_dir))
        print("沙箱环境已重置，所有数据已清除")

    def status(self):
        """查看沙箱环境状态"""
        cmd = [
            "docker-compose",
            "-f",
            str(self.compose_file),
            "ps",
        ]
        subprocess.run(cmd, cwd=str(self.sandbox_dir))

    def logs(self, service: str = None, follow: bool = False):
        """查看沙箱日志"""
        cmd = [
            "docker-compose",
            "-f",
            str(self.compose_file),
            "logs",
        ]
        if follow:
            cmd.append("-f")
        if service:
            cmd.append(service)

        subprocess.run(cmd, cwd=str(self.sandbox_dir))

    def wait_for_health(self, timeout: int = 120):
        """等待沙箱服务健康"""
        start_time = time.time()

        while time.time() - start_time < timeout:
            try:
                with httpx.Client(timeout=5.0) as client:
                    response = client.get(f"{self.api_url}/health")
                    if response.status_code == 200:
                        return True
            except Exception:
                pass
            time.sleep(3)

        raise TimeoutError(
            f"沙箱服务未能在 {timeout} 秒内启动，请检查 Docker 日志: "
            f"docker-compose -f {self.compose_file} logs"
        )

    def get_api_url(self) -> str:
        """获取沙箱 API 地址"""
        return self.api_url

    def run_test(self, video_url: str):
        """在沙箱中运行简单测试"""
        print(f"在沙箱中测试视频: {video_url}")

        try:
            with httpx.Client(timeout=30.0) as client:
                # 提交任务
                response = client.post(
                    f"{self.api_url}/api/v1/breakdown/submit",
                    json={"video_source": video_url},
                )
                result = response.json()

                if result["code"] != 0:
                    print(f"提交失败: {result['message']}")
                    return

                task_id = result["data"]["task_id"]
                print(f"任务已提交，task_id: {task_id}")

                # 轮询等待
                while True:
                    response = client.get(
                        f"{self.api_url}/api/v1/breakdown/status/{task_id}"
                    )
                    status_data = response.json()["data"]

                    current_status = status_data["status"]
                    progress = status_data.get("progress", 0)
                    step = status_data.get("current_step", "unknown")

                    if current_status == "completed":
                        print("任务完成!")
                        # 获取结果
                        response = client.get(
                            f"{self.api_url}/api/v1/breakdown/result/{task_id}"
                        )
                        result_data = response.json()["data"]
                        print(f"  分镜数: {result_data.get('segment_count', 0)}")
                        print(f"  时长: {result_data.get('duration', 0):.1f}s")
                        return task_id
                    elif current_status == "failed":
                        print(
                            f"任务失败: {status_data.get('error_message', '未知错误')}"
                        )
                        return None

                    print(f"  处理中... {progress}% ({step})")
                    time.sleep(5)

        except httpx.ConnectError:
            print(f"无法连接到沙箱 API ({self.api_url})，请确认沙箱已启动")
        except Exception as e:
            print(f"测试异常: {e}")


def main():
    """CLI 入口"""
    manager = SandboxManager()

    if len(sys.argv) < 2:
        print("沙箱环境管理器")
        print()
        print("用法:")
        print("  python sandbox_manager.py start [--rebuild]  启动沙箱")
        print("  python sandbox_manager.py stop               停止沙箱")
        print("  python sandbox_manager.py reset              重置沙箱")
        print("  python sandbox_manager.py status             查看状态")
        print("  python sandbox_manager.py logs [service]     查看日志")
        print("  python sandbox_manager.py test <video_url>   运行测试")
        sys.exit(0)

    command = sys.argv[1]

    if command == "start":
        manager.start(rebuild="--rebuild" in sys.argv)
    elif command == "stop":
        manager.stop()
    elif command == "reset":
        manager.reset()
    elif command == "status":
        manager.status()
    elif command == "logs":
        service = sys.argv[2] if len(sys.argv) > 2 else None
        manager.logs(service=service, follow="-f" in sys.argv)
    elif command == "test":
        if len(sys.argv) < 3:
            print("用法: python sandbox_manager.py test <video_url>")
            sys.exit(1)
        manager.start()
        manager.run_test(sys.argv[2])
    else:
        print(f"未知命令: {command}")
        sys.exit(1)


if __name__ == "__main__":
    main()
