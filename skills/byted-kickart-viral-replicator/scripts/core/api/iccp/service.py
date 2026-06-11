# Copyright 2026 ByteDance
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


import os
import sys
import json
import jsonpath

# 动态加载根目录以便正确导入
sys.path.append(
    os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    )
)
from core import Result
from core.auth.strategy import AuthStrategyFactory
from core.api.iccp.client import IccpClientFactory

# ─── 业务服务层 (Service Layer) ───────────────────────────────────


class IccpService:
    def __init__(self):
        strategy = AuthStrategyFactory.create()
        self.client = IccpClientFactory.create(strategy)

    def submit(self, service_id: int, params: str) -> Result:
        try:
            payload = {
                "ResourceList": [
                    "https://lf3-static.bytednsdoc.com/obj/eden-cn/jhteh7uhpxnult/test_image/woman/woman_4.png"
                ],
                "TemplateId": str(service_id),
                "Resolution": "1080p",
                "Extra": params,
            }

            submit_body = {
                "ServerId": service_id,
                "PayloadJson": json.dumps(payload, ensure_ascii=False),
            }
            submit_bytes = json.dumps(submit_body, ensure_ascii=False).encode("utf-8")

            response = self.client.do_request(
                "POST", {}, submit_bytes, action="SubmitAiTemplateTaskAsync"
            )

            code = jsonpath.jsonpath(response, "$.ResponseMetadata.Code")
            if not code:
                return Result(code="-1", message="提交任务失败, 响应内容为空")
            if code[0] != 0:
                return Result(
                    code=str(code[0]), message=f"提交任务失败, Code: {code[0]}"
                )

            task_id = jsonpath.jsonpath(response, "$.Result.TaskId")
            if not task_id or not task_id[0]:
                return Result(
                    code="-1", message=f"解析TaskId失败, 响应内容: {response}"
                )
            return Result(code="0", message="success", data=task_id[0])
        except Exception as e:
            return Result(code="-1", message=f"提交任务失败, 错误信息: {str(e)}")

    def query(self, task_id: str) -> Result:
        params = json.dumps({"TaskId": task_id}, ensure_ascii=False).encode("utf-8")
        try:
            resp = self.client.do_request(
                "POST", {}, params, action="QueryAiTemplateTaskResult"
            )

            code = jsonpath.jsonpath(resp, "$.ResponseMetadata.Code")
            if not code:
                return Result(code="-1", message="提交任务失败, 响应内容为空")
            if code[0] != 0:
                return Result(
                    code=str(code[0]), message=f"查询任务状态失败, Code: {code[0]}"
                )

            result_code = jsonpath.jsonpath(resp, "$.Result.Code")
            if not result_code:
                return Result(code="-1", message="提交任务失败, 响应内容为空")

            if result_code[0] in [1000, 1600]:
                return Result(code="1000", message="任务正在执行中")
            if result_code[0] != 0:
                msg = jsonpath.jsonpath(resp, "$.Result.Message")
                return Result(
                    code=str(result_code[0]), message=msg[0] if msg else "任务异常"
                )

            progress = jsonpath.jsonpath(resp, "$.Result.Progress")
            if not progress or progress[0] != 100:
                return Result(code="1000", message="任务正在执行中")

            result = jsonpath.jsonpath(resp, "$.Result.ResultExtra")
            if not result or not result[0]:
                return Result(code="-1", message="未获取到任务结果")

            return Result(code="0", message="success", data=result[0])
        except Exception as e:
            return Result(code="-1", message=f"查询任务状态失败: {str(e)}")

    def post(self, action: str, params: bytes) -> Result:
        try:
            resp = self.client.do_request("POST", {}, params, action=action)

            open_top_code = jsonpath.jsonpath(resp, "$.ResponseMetadata.Error.CodeN")
            if open_top_code and open_top_code[0] != 0:
                return Result(code=str(open_top_code[0]), message="")

            code = jsonpath.jsonpath(resp, "$.ResponseMetadata.Code")
            if code and code[0] != 0:
                return Result(code=str(code[0]), message="")

            if code and code[0] == 0:
                result = jsonpath.jsonpath(resp, "$.Result")
                if not result or not result[0]:
                    return Result(code="-1", message="接口返回值解析错误")
                expire = jsonpath.jsonpath(resp, "$.Result.expire_time")
                return Result(code="0", message=str(expire and expire[0]))

            return Result(code="-1", message="接口返回值解析错误")
        except Exception as e:
            return Result(code="-1", message=str(e))
