import os
import sys
import time
import json
import logging
import requests
from enum import Enum
from collections import defaultdict
from typing import Optional
from pydantic import BaseModel, Field
from dotenv import load_dotenv

load_dotenv()


class SkillException(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


class KickartException(SkillException):
    pass


class TaskStatus(Enum):
    RUNNING = 1
    SUCCESS = 2
    FAILED = 3


class TaskInfo(BaseModel):
    task_id: str = Field(..., description="Task ID")
    task_status: TaskStatus = Field(default=TaskStatus.RUNNING, description="Task status")
    payload: dict = Field(default={}, description="Task result")


class ViralReplicator:
    HOST = "https://kickart.volces.com"

    def __init__(self, template_id: str):
        self.template_id = template_id

    def submit(self, params: dict) -> TaskInfo:
        body = defaultdict()
        body["template_id"] = self.template_id
        body["payload"] = params

        headers = defaultdict()
        headers["x-muse-token"] = os.getenv("X_MUSE_TOKEN", "")
        if ppe_env := os.getenv("X_VOLC_ENV"):
            headers["X-TT-Env"] = ppe_env
            headers["X-Use-Ppe"] = "1"

        url = self.HOST + "/openapi/ai_effect/submit/v2"

        logger.info(f"[request] >>> {url} {json.dumps(body, ensure_ascii=False)}")
        logger.info(f"[headers] >>> {json.dumps(dict(headers), ensure_ascii=False)}")
        response = requests.post(url, json=body, headers=headers)
        logger.info(f"[response] <<< {response.status_code} {response.text}")
        response.raise_for_status()

        response_data = response.json()
        if response_data["code"] != 0:
            msg = response_data.get("msg", response_data.get("message", "Unknown error"))
            raise KickartException(str(response_data["code"]), msg)
        task_info = TaskInfo(task_id=response_data["data"]["task_id"])

        return task_info

    def query(self, task_info: TaskInfo) -> TaskInfo:
        headers = defaultdict()
        headers["x-muse-token"] = os.getenv("X_MUSE_TOKEN", "")
        if ppe_env := os.getenv("X_VOLC_ENV"):
            headers["X-TT-Env"] = ppe_env
            headers["X-Use-Ppe"] = "1"

        url = self.HOST + "/openapi/ai_effect/query/v2"
        body = task_info.model_dump(exclude=set(["task_status"]))
        logger.info(f"[request] >>> {url} {json.dumps(body, ensure_ascii=False)}")
        logger.info(f"[headers] >>> {json.dumps(dict(headers), ensure_ascii=False)}")
        response = requests.post(url, json=body, headers=headers)
        logger.info(f"[response] <<< {response.status_code} {response.text}")
        response.raise_for_status()

        response_data = response.json()

        if response_data["code"] == 1000:
            return TaskInfo(task_id=task_info.task_id, task_status=TaskStatus.RUNNING)
        if response_data["code"] != 0:
            raise KickartException(str(response_data["code"]), response_data["message"])

        return TaskInfo(
            task_id=task_info.task_id,
            task_status=TaskStatus.SUCCESS,
            payload=response_data.get("data", {}).get("payload", {}),
        )


def _init_logger() -> logging.Logger:
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)
    handler = logging.StreamHandler()
    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    return logger


logger = _init_logger()


def main():
    import argparse

    parser = argparse.ArgumentParser(description="OpenAPI 异步任务接口连通性校验")
    parser.add_argument("--token", required=True, help="鉴权用的 x-muse-token")
    parser.add_argument("--body", required=True, help="提交接口请求体 JSON 文件路径")
    parser.add_argument("--timeout", type=int, default=30, help="单次 HTTP 请求超时秒数，默认 30")
    parser.add_argument("--poll-interval", type=int, default=30, help="轮询间隔秒数，默认 30")
    parser.add_argument("--max-wait", type=int, default=3600, help="轮询最长等待秒数，默认 3600")
    parser.add_argument("--mode", choices=["submit", "query"], default="submit",
                        help="执行模式：submit（提交+轮询，默认）或 query（仅轮询已有任务）")
    parser.add_argument("--task-id", type=str, default=None,
                        help="query 模式下必传，指定要查询的任务ID")
    args = parser.parse_args()

    os.environ["X_MUSE_TOKEN"] = args.token

    try:
        with open(args.body, "r", encoding="utf-8") as f:
            body = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        logger.error(f"读取请求体失败：{str(e)}")
        sys.exit(1)

    if not isinstance(body, dict) or "template_id" not in body:
        logger.error("请求体校验失败：缺少必传字段 template_id")
        sys.exit(1)

    replicator = ViralReplicator(body["template_id"])

    if args.mode == "query":
        # query 模式：跳过 submit，直接使用已有 task_id 进行轮询
        if not args.task_id:
            logger.error("query 模式下必须通过 --task-id 指定要查询的任务ID")
            sys.exit(1)
        task_info = TaskInfo(task_id=args.task_id)
        logger.info(f"=== query 模式：查询任务 {args.task_id} ===")
    else:
        # submit 模式：先提交任务再轮询
        if not isinstance(body, dict) or "payload" not in body:
            logger.error("请求体校验失败：缺少必传字段 payload")
            sys.exit(1)

        try:
            logger.info("=== [1/2] 提交任务 (submit) ===")
            task_info = replicator.submit(body["payload"])
            logger.info(f"提交成功，task_id = {task_info.task_id}")
        except KickartException as e:
            logger.error(f"提交失败：code={e.code}, message={e.message}")
            sys.exit(1)
        except Exception as e:
            logger.error(f"提交异常：{str(e)}")
            sys.exit(1)

    logger.info("=== 轮询结果 (query) ===")
    deadline = time.time() + args.max_wait
    attempt = 0

    while time.time() < deadline:
        attempt += 1
        logger.info(f"第 {attempt} 次轮询")

        try:
            task_info = replicator.query(task_info)
        except KickartException as e:
            logger.error(f"轮询失败：code={e.code}, message={e.message}")
            sys.exit(1)
        except Exception as e:
            logger.error(f"轮询异常：{str(e)}")
            time.sleep(args.poll_interval)
            continue

        logger.info(f"第 {attempt} 次轮询：status={task_info.task_status.name}")

        if task_info.task_status == TaskStatus.SUCCESS:
            logger.info(f"\n任务成功，最终结果:\n{json.dumps(task_info.payload, ensure_ascii=False, indent=2)}")
            sys.exit(0)
        if task_info.task_status == TaskStatus.FAILED:
            logger.error("\n任务失败")
            sys.exit(1)

        time.sleep(args.poll_interval)

    logger.error(f"\n轮询超时（超过 {args.max_wait}s 仍未拿到终态）")
    sys.exit(1)


if __name__ == "__main__":
    main()
