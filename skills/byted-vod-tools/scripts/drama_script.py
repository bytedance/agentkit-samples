#!/usr/bin/env python3
# Copyright (c) 2025 Beijing Volcano Engine Technology Co., Ltd. and/or its affiliates.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""
drama_script.py — 提交 AI 剧本还原任务（CreateDramaScriptTask / QueryDramaScriptTask）

基于大模型视频理解，将剧情类视频转化为结构化剧本文本。精准识别并提取视频中的
场景、人物（角色）、对话、情节等核心元素，为内容创作者和数据分析师提供高价值文本素材。

用法:
  python <SKILL_DIR>/scripts/drama_script.py '<json_args>' [space_name]
  python <SKILL_DIR>/scripts/drama_script.py @params.json [space_name]

JSON 参数说明:
  必选:
    Vids           — 视频 ID 列表（至少 1 个），如 ["v023xxx", "v024xxx"]
  可选:
    ClientToken    — 幂等 token（不传则自动生成 UUID）

输出:
  成功: {"Status":"success","TaskId":"...","ResultUrl":"..."}
  失败: {"error":"..."}
  超时: {"error":"轮询超时...","resume_hint":{"command":"python .../drama_script.py --poll <TaskId> <space>"}}

恢复轮询模式:
  python <SKILL_DIR>/scripts/drama_script.py --poll <TaskId> [space_name]
"""

import sys
import os
import json
import time
import uuid

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from vod_common import (
    init_and_parse,
    get_space_name,
    log,
    bail,
    out,
    POLL_INTERVAL,
    POLL_MAX,
)
from api_manage import ApiManage


# ══════════════════════════════════════════════════════
# 剧本还原任务轮询
# ══════════════════════════════════════════════════════


def poll_drama_script(api, task_id: str, space_name: str) -> dict:
    """
    轮询 QueryDramaScriptTask，终态：success / failed / timeout。

    状态机：
      running  → 继续等待
      success  → 终态成功，返回 ResultUrl
      failed   → 终态失败
      timeout  → 终态超时（服务端超时，非客户端轮询超时）
    """
    TERMINAL_SUCCESS = {"success"}
    TERMINAL_FAIL = {"failed", "timeout"}

    for i in range(1, POLL_MAX + 1):
        log(f"轮询剧本还原任务 [{i}/{POLL_MAX}] TaskId={task_id}")
        try:
            raw = api.query_drama_script_task(
                {
                    "SpaceName": space_name,
                    "TaskId": task_id,
                }
            )
            if isinstance(raw, str):
                raw = json.loads(raw)
        except Exception as e:
            log(f"  查询失败: {e}，等待 {POLL_INTERVAL}s 后重试...")
            time.sleep(POLL_INTERVAL)
            continue

        result = raw.get("Result", raw)
        status = result.get("Status", "")

        if status in TERMINAL_SUCCESS:
            result_url = result.get("ResultUrl", "")
            return {
                "Status": "success",
                "TaskId": task_id,
                "SpaceName": space_name,
                "ResultUrl": result_url,
                "note": (
                    "ResultUrl 是一个 .json.gz 压缩文件的下载链接（有效期 24 小时）。"
                    "直接将此链接提供给用户，不需要下载或解压。"
                ),
            }

        if status in TERMINAL_FAIL:
            return {
                "Status": status,
                "TaskId": task_id,
                "SpaceName": space_name,
                "detail": result,
                "note": "任务失败，请检查输入视频是否满足限制条件后重新提交。"
                if status == "failed"
                else "任务服务端超时，请稍后重新提交。",
            }

        # running 或其他中间状态
        log(f"  状态={status!r}，等待 {POLL_INTERVAL}s ...")
        time.sleep(POLL_INTERVAL)

    # 客户端轮询超时
    return {
        "error": f"轮询超时（{POLL_MAX} 次 × {POLL_INTERVAL}s），任务仍在处理中",
        "TaskId": task_id,
        "resume_hint": {
            "description": "任务尚未完成，可用以下命令重启轮询",
            "command": f"python <SKILL_DIR>/scripts/drama_script.py --poll '{task_id}' {space_name}",
        },
    }


# ══════════════════════════════════════════════════════
# 主流程
# ══════════════════════════════════════════════════════


def main():
    # 检查是否为恢复轮询模式
    if len(sys.argv) > 1 and sys.argv[1] == "--poll":
        if len(sys.argv) < 3:
            bail("恢复轮询用法: python drama_script.py --poll <TaskId> [space_name]")
        task_id = sys.argv[2]
        api = ApiManage()
        sp = get_space_name(argv_pos=3)
        log(f"恢复轮询剧本还原任务：TaskId={task_id}, SpaceName={sp}")
        result = poll_drama_script(api, task_id, sp)
        out(result)
        return

    api, space_name, args = init_and_parse(argv_pos=1)

    # ── 解析 Vids ──
    vids = args.get("Vids") or args.get("vids") or []
    # 兼容单个 vid 字符串
    if isinstance(vids, str):
        vids = [vids]
    if not vids:
        bail("必须提供 Vids 参数（视频 ID 列表），至少包含 1 个视频 ID")

    # 过滤空值
    vids = [v for v in vids if v]
    if not vids:
        bail("Vids 列表中没有有效的视频 ID")

    # ── 幂等 token ──
    client_token = args.get("ClientToken") or str(uuid.uuid4())

    # ── 构造请求体 ──
    body = {
        "SpaceName": space_name,
        "Vids": vids,
        "ClientToken": client_token,
    }

    log(f"提交剧本还原任务: {len(vids)} 个视频, SpaceName={space_name}")

    # ── 提交任务 ──
    try:
        raw = api.create_drama_script_task(body)
        if isinstance(raw, str):
            raw = json.loads(raw)
    except Exception as e:
        bail(f"提交剧本还原任务失败: {e}")

    result = raw.get("Result", raw)
    task_id = result.get("TaskId", "")
    if not task_id:
        bail(f"提交任务未返回 TaskId，原始响应：{json.dumps(raw, ensure_ascii=False)}")

    log(f"任务已提交，TaskId={task_id}，开始轮询...")

    # ── 轮询直到终态 ──
    poll_result = poll_drama_script(api, task_id, space_name)
    out(poll_result)


if __name__ == "__main__":
    main()
