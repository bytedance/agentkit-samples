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

import os
import hmac
import hashlib
import json
import jsonpath
import time
from urllib.parse import urlencode, urlparse
import requests
import argparse



# 输出错误信息（JSON格式）
def output_error(code, error_msg):

    if (code == -1):
        print(error_msg)
    else:
        print("阅读并参考`./references/接口错误指南.md，根据错误码{}进行处理`".format(code))


ACCESS_KEY_ID = os.getenv("ACCESS_KEY_ID") or ""
SECRET_ACCESS_KEY = os.getenv("SECRET_ACCESS_KEY") or ""

if ACCESS_KEY_ID == "" or SECRET_ACCESS_KEY == "":
    print("请提供火山引擎的 App Key 和 Secret Key!")
    exit(1)
# 请求地址
ADDR = "https://icp.volcengineapi.com"

# 请求接口信息
SERVICE = "iccloud_muse"
REGION = "cn-north"
ACTION = "SubmitAiTemplateTaskAsync"
VERSION = "2025-11-25"

# 轮询次数 30, 轮询间隔 2S
POLL_MAX_ATTEMPTS = 60 * 4
POLL_INTERVAL_SECONDS = 5


# 构造header Authorization
def hmac_sha256(key: bytes, content: str) -> bytes:
    """HMAC-SHA256加密"""
    h = hmac.new(key, content.encode("utf-8"), hashlib.sha256)
    return h.digest()

def get_signed_key(secret_key: str, date: str, region: str, service: str) -> bytes:
    """生成签名密钥链"""
    k_date = hmac_sha256(secret_key.encode("utf-8"), date)
    k_region = hmac_sha256(k_date, region)
    k_service = hmac_sha256(k_region, service)
    k_signing = hmac_sha256(k_service, "request")
    return k_signing

def hash_sha256(data: bytes) -> bytes:
    """SHA256哈希"""
    h = hashlib.sha256()
    h.update(data)
    return h.digest()

# 请求示例
def do_request(method: str, queries: dict, body: bytes, action: str, version: str = VERSION):
    """发起请求（支持GET/POST，包含签名逻辑）"""
    # 1. 处理查询参数，添加Action和Version
    queries["Action"] = action or ACTION
    queries["Version"] = version or VERSION

    # 构建请求地址
    query_string = urlencode(queries)
    query_string = query_string.replace("+", "%20")
    url = f"{ADDR}?{query_string}"

    # 2. 构建签名核心材料
    date = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime(time.time()))
    auth_date = date[:8]  # 提取日期部分（YYYYMMDD）

    # 计算请求体哈希
    payload = hash_sha256(body).hex()

    # 构建签名头部列表
    signed_headers = ["host", "x-date", "x-content-sha256", "content-type"]
    parsed_url = urlparse(ADDR)
    host = parsed_url.netloc  # 提取主机名（如：icp.volcengineapi.com）

    # 构建规范头部字符串
    header_list = []
    for header in signed_headers:
        if header == "host":
            header_list.append(f"{header}:{host}")
        elif header == "x-date":
            header_list.append(f"{header}:{date}")
        elif header == "x-content-sha256":
            header_list.append(f"{header}:{payload}")
        elif header == "content-type":
            header_list.append(f"{header}:application/json")
    header_string = "\n".join(header_list)

    # 构建规范请求字符串
    canonical_string = "\n".join([method.upper(),"/",query_string,f"{header_string}\n",";".join(signed_headers),payload])
    hashed_canonical_string = hash_sha256(canonical_string.encode("utf-8")).hex()
    credential_scope = f"{auth_date}/{REGION}/{SERVICE}/request"
    sign_string = "\n".join(["HMAC-SHA256",date,credential_scope,hashed_canonical_string])
    signed_key = get_signed_key(SECRET_ACCESS_KEY, auth_date, REGION, SERVICE)
    signature = hmac_sha256(signed_key, sign_string).hex()
    authorization = (f"HMAC-SHA256 Credential={ACCESS_KEY_ID}/{credential_scope},"f" SignedHeaders={';'.join(signed_headers)},"f" Signature={signature}")

    # 4. 构建完整请求头
    headers = {
        "X-Date": date,
        "X-Content-Sha256": payload,
        "Content-Type": "application/json",
        "Authorization": authorization,
        "X-TT-Env": "ppe_volcengine",
        "X-Volc-Env": "ppe_ic_arkclaw",
        "X-Use-Ppe": "1"
    }

    # 6. 发起请求并处理响应
    try:
        response = requests.request(method=method.upper(),url=url,headers=headers,data=body,timeout=30)
    except Exception as e:
        output_error(-1, f"do request err: {str(e)}")
        exit(1)

    # 输出请求结果
    if response is None:
        output_error(-1, "请求失败（响应为空）")
        exit(1)
    if response.status_code != 200:
        output_error(-1, f"请求失败（状态码：{response.status_code}）, 响应内容: {response.text}")
        exit(1)

    return response

# 发起请求 获取 TaskID
def submit(args: argparse.Namespace):
    payload = {
        "ResourceList": ["https://lf3-static.bytednsdoc.com/obj/eden-cn/jhteh7uhpxnult/test_image/woman/woman_4.png"],
        "TemplateId": "2000620034",
        "Resolution": "1080p",
        "Extra": args.params,
    }
    # 图生图 样例
    submit_body = {
        "ServerId": args.service_id,
        "PayloadJson": json.dumps(payload, ensure_ascii=False),
    }
    submit_bytes = json.dumps(submit_body, ensure_ascii=False).encode("utf-8")
    response = do_request("POST", {}, submit_bytes, action="SubmitAiTemplateTaskAsync")

    try:
        task_id = response.json().get("Result", {}).get("TaskId")
        return task_id
    except Exception as e:
        output_error(-1, f"解析TaskId失败: {str(e)}")
        exit(1)


# 轮询查询任务状态
def poll(task_id: str):
    params = json.dumps({"TaskId": task_id}, ensure_ascii=False).encode("utf-8")
    try:
        for _ in range(POLL_MAX_ATTEMPTS):
            time.sleep(POLL_INTERVAL_SECONDS)

            resp = do_request("POST", {}, params, action="QueryAiTemplateTaskResult").json()

            code = jsonpath.jsonpath(resp, "$.ResponseMetadata.Code")
            if not code or code[0] != 0:
                output_error(code, f"查询任务状态失败, Code: {code}")
                exit(1)
            
            result_code = jsonpath.jsonpath(resp, "$.Result.Code")
            progress = jsonpath.jsonpath(resp, "$.Result.Progress")
            
            # 任务进行中, 继续轮询
            if result_code and result_code[0] == 1000: continue
            # 任务不存在，继续轮询
            if result_code and result_code[0] == 1600: continue

            # 任务成功
            if result_code and result_code[0] == 0 and progress and progress[0] == 100:
                result = jsonpath.jsonpath(resp, "$.Result.ResultExtra")
                if not result or not result[0]:
                    output_error(-1, "查询任务状态失败, Code: 0000, 返回结果为空")
                    exit(1)
                return json.loads(result[0])
                          
            # 任务异常: 未开通套餐
            if result_code and result_code[0] == 1501:
                output_error(result_code[0], f"查询任务状态失败, Code: {result_code[0]}, 用户套餐过期，请升级套餐～")
                exit(1)
            
            # 任务异常: 创点不足
            if result_code and result_code[0] == 1402:
                output_error(result_code[0], f"查询任务状态失败, Code: {result_code[0]}, 用户创点不足, 请充值套餐～")
                exit(1)

            # 其他异常
            # print(resp, file=sys.stderr)
            output_error(-1, f"查询任务状态失败, Code: {result_code and result_code[0]}")
            exit(1)

        raise Exception("超过最大重试次数！")
    except Exception as e:
        if str(e) == "超过最大重试次数！":
            output_error(-1, str(e))
        else:
            output_error(-1, f"轮询查询任务状态失败: {str(e)}")
        exit(1)

# 查询&注册免费的Ark Claw 套餐
def register_ark_claw_combo():
    resp = do_request("POST", {}, b'', action="RegisterArkClawCombo").json()
    # print(f"RegisterArkClawCombo Response: {resp}")

    try:
        code = jsonpath.jsonpath(resp, "$.ResponseMetadata.Code")
        # print(f"RegisterArkClawCombo Code: {code}")
        # 任务成功
        if code and code[0] == 0:
            result = jsonpath.jsonpath(resp, "$.Result")
            if not result or not result[0]:
                output_error(code[0], f"查询套餐信息失败, Code: {code[0]}, 返回结果为空")
                exit(1)
            else:
                result_data = result[0]
                print(f"当前套餐有效， 套餐信息: {result_data}")
                return result_data

        # 任务异常: 未开通套餐
        if code and code[0] == 1501:
            output_error(code[0], f"查询套餐信息失败, Code: {code[0]}, 用户套餐过期，请升级套餐～")
            exit(1)
        
        # 任务异常: 创点不足
        if code and code[0] == 1402:
            output_error(code[0], f"查询套餐信息失败, Code: {code[0]}, 用户创点不足, 请充值套餐～")
            exit(1)
    except Exception as e:
        output_error(-1, f"查询套餐信息失败: {str(e)}")
        exit(1)



def load_params(args: argparse.Namespace) -> str:
    if not args.input and not args.params:
        output_error(-1, "未指定params参数或json文件路径!")
        exit(1)
    if args.input:
        try:
            with open(args.input, "r") as f:
                result = f.read()
            if args.forward == "storyboard":
                result = json.loads(result)
                result = jsonpath.jsonpath(result, "$.storyboards.0")
                result = json.dumps(result and result[0], ensure_ascii=False)
            return result
        except Exception as e:
            output_error(-1, f"读取json文件失败: {str(e)}")
            exit(1)    
    return args.params


### 命令行参数
parser = argparse.ArgumentParser(description="调用创作云服务")
parser.add_argument("--service-id", required=False, type=int, help="创作云的服务ID，从指南中获取")
parser.add_argument("--params", required=False, type=str, default=None, help="输入JSON格式的参数, 与--input二选一")
parser.add_argument("--input", required=False, type=str, default=None, help="从json文件中读取params参数, 与--params二选一")
parser.add_argument("--output", required=False, type=str, help="输出结果所在的json文件路径")
parser.add_argument("--register-combo", action="store_true", help="查询或注册ArkClaw免费套餐")
parser.add_argument("--forward", required=False, type=str, default=None, help="前置处理流程")
args = parser.parse_args()

### 主流程
if args.register_combo:
    register_ark_claw_combo()
else:
    if args.service_id is None:
        parser.error("--service-id is required when not using --register-combo")
    args.params = load_params(args)
    poll_result = poll(submit(args))
    with open(args.output, "w") as f:
        json.dump(poll_result, f, ensure_ascii=False, indent=2)
    print(f"任务状态查询完成, 结果已保存到: {args.output}")
