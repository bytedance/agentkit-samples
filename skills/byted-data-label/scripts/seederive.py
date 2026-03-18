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

#!/usr/bin/env python3
"""
Seederive CLI — 统一的 API 调用脚本

Agent 和用户通过本脚本与 Seederive OpenAPI 交互，无需手动拼 URL / Header / JSON Body。

用法：
    python seederive.py <子命令> <操作> [参数...]

子命令：
    task        任务管理
    prompt      提示词管理
    error-case  错题管理
    model       模型管理
    tag-base    标签库管理

环境变量（也可通过 --base-url 参数覆盖）：
    VOLCENGINE_ACCESS_KEY   火山引擎 Access Key
    VOLCENGINE_SECRET_KEY   火山引擎 Secret Key
    SEEDERIVE_BASE_URL      API 基础地址（可选）
"""

import argparse
import json
import os
import sys
from urllib.parse import urljoin

try:
    import requests
except ImportError:
    print("缺少 requests 库，正在安装...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "requests", "-q"])
    import requests


# ============================== 全局配置 ==============================

DEFAULT_BASE_URL = "https://sd6qlcofkmfq59riqgli0.apigateway-cn-beijing.volceapi.com"
API_PREFIX = "/profile_platform/openapi/v2/seederive"



def get_config(args):
    """从参数和环境变量构建配置"""
    base_url = getattr(args, "base_url", None) or os.environ.get("SEEDERIVE_BASE_URL", DEFAULT_BASE_URL)

    access_key = os.environ.get("VOLCENGINE_ACCESS_KEY", "")
    secret_key = os.environ.get("VOLCENGINE_SECRET_KEY", "")

    if not access_key or not secret_key:
        print("错误：未提供认证凭证。请设置环境变量 VOLCENGINE_ACCESS_KEY 和 VOLCENGINE_SECRET_KEY",
              file=sys.stderr)
        sys.exit(1)

    return {
        "access_key": access_key,
        "secret_key": secret_key,
        "base_url": base_url.rstrip("/"),
    }


# ============================== HTTP 工具 ==============================

def _url(config, path):
    return config["base_url"] + API_PREFIX + path


def _headers(config, extra=None):
    h = {
        "Volc-Access-Key": config["access_key"],
        "Volc-Secret-Key": config["secret_key"],
    }
    if extra:
        h.update(extra)
    return h


def _json_headers(config):
    return _headers(config, {"Content-Type": "application/json"})


def _print_response(resp):
    """统一输出响应"""
    try:
        data = resp.json()
        print(json.dumps(data, ensure_ascii=False, indent=2))
    except Exception:
        data = None
        print(f"HTTP {resp.status_code}")
        print(resp.text)
    if resp.status_code >= 400:
        sys.exit(1)
    # 业务错误码检查：HTTP 200 但 code != 0 视为失败
    if isinstance(data, dict) and "code" in data and data["code"] != 0:
        sys.exit(1)


def _get(config, path, params=None):
    resp = requests.get(_url(config, path), headers=_headers(config), params=params)
    _print_response(resp)
    return resp


def _post_json(config, path, body):
    resp = requests.post(_url(config, path), headers=_json_headers(config), json=body)
    _print_response(resp)
    return resp


def _put_json(config, path, body):
    resp = requests.put(_url(config, path), headers=_json_headers(config), json=body)
    _print_response(resp)
    return resp


def _delete(config, path, body=None):
    if body is not None:
        resp = requests.delete(_url(config, path), headers=_json_headers(config), json=body)
    else:
        resp = requests.delete(_url(config, path), headers=_headers(config))
    _print_response(resp)
    return resp


def _post_file(config, path, file_path, extra_fields=None):
    if not os.path.isfile(file_path):
        print(f"错误：文件不存在 {file_path}", file=sys.stderr)
        sys.exit(1)
    with open(file_path, "rb") as f:
        files = {"file": (os.path.basename(file_path), f)}
        data = extra_fields or {}
        resp = requests.post(_url(config, path), headers=_headers(config), files=files, data=data)
    _print_response(resp)
    return resp


# ============================== task 子命令 ==============================

def task_create(args, config):
    """创建任务"""
    body = {"name": args.name}
    if args.description:
        body["description"] = args.description
    if args.flow_config:
        body["taskFlowConfig"] = json.loads(args.flow_config)
    if args.flow_config_file:
        with open(args.flow_config_file) as f:
            body["taskFlowConfig"] = json.load(f)
    if args.schedule_type:
        body["scheduleConfig"] = {"type": args.schedule_type}
    _post_json(config, "/task", body)


def task_update(args, config):
    """更新任务"""
    body = {}
    if args.name:
        body["name"] = args.name
    if args.description:
        body["description"] = args.description
    if args.flow_config:
        body["taskFlowConfig"] = json.loads(args.flow_config)
    if args.flow_config_file:
        with open(args.flow_config_file) as f:
            body["taskFlowConfig"] = json.load(f)
    _put_json(config, f"/task/{args.id}", body)


def task_delete(args, config):
    """删除任务"""
    _delete(config, f"/task/{args.id}")


def task_get(args, config):
    """获取任务详情"""
    _get(config, f"/task/{args.id}")


def task_list(args, config):
    """获取任务列表"""
    params = {}
    if args.keyword:
        params["keyword"] = args.keyword
    if args.creator:
        params["creator"] = args.creator
    if args.name:
        params["name"] = args.name
    params["page"] = args.page
    params["pageSize"] = args.page_size
    _get(config, "/task/list", params)


def task_backfill(args, config):
    """任务回填"""
    body = {"bdbTaskId": args.bdb_task_id}
    if args.start_time:
        body["startTaskTime"] = args.start_time
    if args.end_time:
        body["endTaskTime"] = args.end_time
    _post_json(config, "/task/backfill", body)


def task_preview(args, config):
    """数据预览"""
    body = {"limit": args.limit}
    if args.input_dataset:
        body["inputDataSet"] = json.loads(args.input_dataset)
    if args.input_dataset_file:
        with open(args.input_dataset_file) as f:
            body["inputDataSet"] = json.load(f)
    _post_json(config, "/task/preview", body)


def task_result(args, config):
    """结果预览"""
    body = {"taskId": args.task_id}
    if args.page_num:
        body["pageNum"] = args.page_num
    if args.page_size:
        body["pageSize"] = args.page_size
    if args.partition:
        body["partition"] = json.loads(args.partition)
    _post_json(config, "/task/resultPreview", body)


def task_quick_preview(args, config):
    """轻量预览"""
    resp_format = getattr(args, "response_format", "json") or "json"

    def _handle_response(resp):
        if resp_format == "csv" and resp.status_code == 200:
            out = args.output or "quick_preview_result.csv"
            with open(out, "wb") as f:
                f.write(resp.content)
            print(f"结果已保存到 {out}")
        else:
            _print_response(resp)

    # rawData 模式：JSON body（二维数组 + columns）
    raw_data_str = args.raw_data
    if not raw_data_str and args.raw_data_file:
        with open(args.raw_data_file) as f:
            raw_data_str = f.read()

    if raw_data_str:
        parsed = json.loads(raw_data_str)
        # 自动推断 columns 和 rawData 格式
        if parsed and isinstance(parsed[0], dict):
            # 对象数组 [{"col1":"v1"}, ...] → 提取 columns + 转二维数组
            col_set = []
            for obj in parsed:
                for k in obj:
                    if k not in col_set:
                        col_set.append(k)
            columns = col_set
            raw_rows = [[str(obj.get(c, "")) if obj.get(c) is not None else "" for c in columns] for obj in parsed]
        elif parsed and isinstance(parsed[0], list):
            # 已经是二维数组，需要用户提供 --columns 或默认用 inputColumn
            if args.columns:
                columns = json.loads(args.columns)
            else:
                columns = [args.input_column]
            raw_rows = parsed
        else:
            # 字符串数组 ["文本1", ...] → 单列二维数组
            columns = [args.input_column]
            raw_rows = [[str(item)] for item in parsed]

        body = {
            "nodeType": args.node_type,
            "inputColumns": [args.input_column],
            "columns": columns,
            "rawData": raw_rows,
            "responseFormat": resp_format,
        }
        if args.max_rows is not None:
            body["maxRows"] = args.max_rows
        if args.tag_base_id is not None:
            body["tagBaseId"] = args.tag_base_id
        if args.prompt:
            body["prompt"] = args.prompt
        if args.output_fields:
            body["outputFields"] = args.output_fields
        if args.target_language:
            body["targetLanguage"] = args.target_language

        if resp_format == "csv":
            resp = requests.post(
                _url(config, "/task/quick-preview"),
                headers=_json_headers(config),
                json=body,
            )
            _handle_response(resp)
        else:
            _post_json(config, "/task/quick-preview", body)
        return

    # 文件模式：multipart/form-data
    if not args.file:
        print("错误：--file 和 --raw-data 至少提供一个", file=sys.stderr)
        sys.exit(1)
    if not os.path.isfile(args.file):
        print(f"错误：文件不存在 {args.file}", file=sys.stderr)
        sys.exit(1)
    extra = {
        "nodeType": args.node_type,
        "inputColumns": args.input_column,
        "responseFormat": resp_format,
    }
    if args.max_rows is not None:
        extra["maxRows"] = str(args.max_rows)
    if args.tag_base_id is not None:
        extra["tagBaseId"] = str(args.tag_base_id)
    if args.prompt:
        extra["prompt"] = args.prompt
    if args.output_fields:
        extra["outputFields"] = args.output_fields
    if args.target_language:
        extra["targetLanguage"] = args.target_language
    with open(args.file, "rb") as f:
        files = {"file": (os.path.basename(args.file), f)}
        resp = requests.post(
            _url(config, "/task/quick-preview"),
            headers=_headers(config),
            files=files,
            data=extra,
        )
    _handle_response(resp)


def register_task(subparsers):
    task_parser = subparsers.add_parser("task", help="任务管理")
    task_sub = task_parser.add_subparsers(dest="action")

    # create
    p = task_sub.add_parser("create", help="创建任务")
    p.add_argument("--name", required=True, help="任务名称")
    p.add_argument("--description", help="任务描述")
    p.add_argument("--flow-config", help="taskFlowConfig JSON 字符串")
    p.add_argument("--flow-config-file", help="taskFlowConfig JSON 文件路径")
    p.add_argument("--schedule-type", default="MANUAL", help="调度类型（默认 MANUAL）")

    # update
    p = task_sub.add_parser("update", help="更新任务")
    p.add_argument("--id", required=True, type=int, help="任务ID")
    p.add_argument("--name", help="新的任务名称")
    p.add_argument("--description", help="新的任务描述")
    p.add_argument("--flow-config", help="taskFlowConfig JSON 字符串")
    p.add_argument("--flow-config-file", help="taskFlowConfig JSON 文件路径")

    # delete
    p = task_sub.add_parser("delete", help="删除任务")
    p.add_argument("--id", required=True, type=int, help="任务ID")

    # get
    p = task_sub.add_parser("get", help="获取任务详情")
    p.add_argument("--id", required=True, type=int, help="任务ID")

    # list
    p = task_sub.add_parser("list", help="获取任务列表")
    p.add_argument("--keyword", help="关键字搜索")
    p.add_argument("--creator", help="按创建人过滤")
    p.add_argument("--name", help="按名称过滤")
    p.add_argument("--page", type=int, default=1, help="页码（默认 1）")
    p.add_argument("--page-size", type=int, default=20, help="每页条数（默认 20）")

    # backfill
    p = task_sub.add_parser("backfill", help="任务回填")
    p.add_argument("--bdb-task-id", required=True, type=int, help="BDB 任务 ID")
    p.add_argument("--start-time", help="开始时间")
    p.add_argument("--end-time", help="结束时间")

    # preview
    p = task_sub.add_parser("preview", help="数据预览")
    p.add_argument("--input-dataset", help="inputDataSet JSON 字符串")
    p.add_argument("--input-dataset-file", help="inputDataSet JSON 文件路径")
    p.add_argument("--limit", type=int, default=10, help="预览行数（默认 10）")

    # result
    p = task_sub.add_parser("result", help="查看任务结果")
    p.add_argument("--task-id", required=True, type=int, help="任务ID")
    p.add_argument("--page-num", type=int, help="页码")
    p.add_argument("--page-size", type=int, help="每页条数")
    p.add_argument("--partition", help="分区 JSON（如 '{\"p_date\":\"2025-01-01\"}'）")

    # quick-preview
    p = task_sub.add_parser("quick-preview", help="轻量预览（上传文件或传原始数据 + 指定节点即可预览结果）")
    p.add_argument("--file", help="CSV 或 Excel 文件路径（与 --raw-data 二选一）")
    p.add_argument("--raw-data", help="原始数据 JSON 数组（如 '[\"文本1\",\"文本2\"]'，与 --file 二选一）")
    p.add_argument("--raw-data-file", help="原始数据 JSON 文件路径（与 --file / --raw-data 二选一）")
    p.add_argument("--columns", help="列名 JSON 数组（rawData 为二维数组时需要，如 '[\"评论内容\",\"用户\"]'）")
    p.add_argument("--node-type", required=True, help="节点类型（如 EMOTION_DETECTION）")
    p.add_argument("--input-column", required=True, help="作为待处理文本的列名")
    p.add_argument("--max-rows", type=int, help="最大处理行数（默认 10，上限 50）")
    p.add_argument("--tag-base-id", type=int, help="标签库 ID（TAG_DETECTION / SUBJECT_DETECTION 需要）")
    p.add_argument("--prompt", help="自定义提示词（CUSTOM_APPLICATION 需要）")
    p.add_argument("--output-fields", help="输出字段 JSON 数组（CUSTOM_APPLICATION 需要）")
    p.add_argument("--target-language", help="翻译目标语言（TRANSLATION 用，默认\"中文\"）")
    p.add_argument("--response-format", choices=["json", "csv"], default="json",
                   help="响应格式：json（默认）或 csv（返回文件下载）")
    p.add_argument("--output", help="CSV 输出文件路径（默认 quick_preview_result.csv）")


TASK_ACTIONS = {
    "create": task_create,
    "update": task_update,
    "delete": task_delete,
    "get": task_get,
    "list": task_list,
    "backfill": task_backfill,
    "preview": task_preview,
    "result": task_result,
    "quick-preview": task_quick_preview,
}


# ============================== prompt 子命令 ==============================

def prompt_detail(args, config):
    """查询提示词详情"""
    _get(config, "/prompt/detail", {"taskId": args.task_id, "nodeId": args.node_id})


def prompt_generate(args, config):
    """生成提示词"""
    _post_json(config, "/prompt/generate", {"description": args.description})


def prompt_optimize(args, config):
    """触发提示词优化"""
    _post_json(config, "/prompt/optimize", {"taskId": args.task_id})


def prompt_report(args, config):
    """查询优化报告"""
    body = {}
    if args.task_id:
        body["taskId"] = args.task_id
    if args.node_id:
        body["nodeId"] = args.node_id
    if args.prompt_id:
        body["promptId"] = args.prompt_id
    if args.version:
        body["version"] = args.version
    _post_json(config, "/prompt/optimize/report", body)


def register_prompt(subparsers):
    prompt_parser = subparsers.add_parser("prompt", help="提示词管理")
    prompt_sub = prompt_parser.add_subparsers(dest="action")

    # detail
    p = prompt_sub.add_parser("detail", help="查询提示词详情")
    p.add_argument("--task-id", required=True, type=int, help="任务ID")
    p.add_argument("--node-id", required=True, help="节点ID")

    # generate
    p = prompt_sub.add_parser("generate", help="生成提示词")
    p.add_argument("--description", required=True, help="提示词描述")

    # optimize
    p = prompt_sub.add_parser("optimize", help="触发提示词优化")
    p.add_argument("--task-id", required=True, type=int, help="任务ID")

    # report
    p = prompt_sub.add_parser("report", help="查询优化报告")
    p.add_argument("--task-id", type=int, help="任务ID")
    p.add_argument("--node-id", help="节点ID")
    p.add_argument("--prompt-id", type=int, help="提示词ID")
    p.add_argument("--version", type=int, help="版本号")


PROMPT_ACTIONS = {
    "detail": prompt_detail,
    "generate": prompt_generate,
    "optimize": prompt_optimize,
    "report": prompt_report,
}


# ============================== error-case 子命令 ==============================

def ec_create_text(args, config):
    """上传错题（文本）"""
    body = {"taskId": args.task_id, "nodeId": args.node_id, "items": []}
    if args.items:
        body["items"] = json.loads(args.items)
    if args.items_file:
        with open(args.items_file) as f:
            body["items"] = json.load(f)
    _post_json(config, "/error-case/create/text", body)


def ec_create_file(args, config):
    """上传错题（文件）"""
    _post_file(config, "/error-case/create/file", args.file, {"taskId": str(args.task_id)})


def ec_list(args, config):
    """查询错题列表"""
    params = {"taskId": args.task_id, "page": args.page, "pageSize": args.page_size}
    if args.trace_id:
        params["traceId"] = args.trace_id
    if args.creator:
        params["creator"] = args.creator
    _get(config, "/error-case/list", params)


def ec_delete(args, config):
    """删除错题"""
    ids = [int(x) for x in args.ids.split(",")]
    _delete(config, "/error-case/delete", ids)


def ec_template(args, config):
    """下载错题模板"""
    resp = requests.get(
        _url(config, "/error-case/template"),
        headers=_headers(config),
        params={"format": args.format},
    )
    if resp.status_code == 200:
        out = args.output or f"error_case_template.{args.format}"
        with open(out, "wb") as f:
            f.write(resp.content)
        print(f"模板已保存到 {out}")
    else:
        _print_response(resp)


def register_error_case(subparsers):
    ec_parser = subparsers.add_parser("error-case", help="错题管理")
    ec_sub = ec_parser.add_subparsers(dest="action")

    # create-text
    p = ec_sub.add_parser("create-text", help="上传错题（文本）")
    p.add_argument("--task-id", required=True, type=int, help="任务ID")
    p.add_argument("--node-id", required=True, help="节点ID")
    p.add_argument("--items", help="错题项 JSON 数组")
    p.add_argument("--items-file", help="错题项 JSON 文件路径")

    # create-file
    p = ec_sub.add_parser("create-file", help="上传错题（文件）")
    p.add_argument("--task-id", required=True, type=int, help="任务ID")
    p.add_argument("--file", required=True, help="错题文件路径（CSV/Excel）")

    # list
    p = ec_sub.add_parser("list", help="查询错题列表")
    p.add_argument("--task-id", required=True, type=int, help="任务ID")
    p.add_argument("--trace-id", help="traceId 过滤")
    p.add_argument("--creator", help="创建人过滤")
    p.add_argument("--page", type=int, default=1, help="页码")
    p.add_argument("--page-size", type=int, default=20, help="每页条数")

    # delete
    p = ec_sub.add_parser("delete", help="删除错题")
    p.add_argument("--ids", required=True, help="错题ID列表，逗号分隔（如 1,2,3）")

    # template
    p = ec_sub.add_parser("template", help="下载错题模板")
    p.add_argument("--format", default="csv", choices=["csv", "xlsx"], help="模板格式")
    p.add_argument("--output", help="保存路径")


EC_ACTIONS = {
    "create-text": ec_create_text,
    "create-file": ec_create_file,
    "list": ec_list,
    "delete": ec_delete,
    "template": ec_template,
}


# ============================== model 子命令 ==============================

def model_list(args, config):
    """查询模型列表"""
    params = {}
    if args.enabled is not None:
        params["enabled"] = str(args.enabled).lower()
    if args.model_name:
        params["modelName"] = args.model_name
    _get(config, "/models", params)


def model_set_node(args, config):
    """修改节点模型配置"""
    body = {}
    if args.model_id:
        body["modelId"] = args.model_id
    if args.temperature is not None:
        body["overrideTemperature"] = args.temperature
    if args.max_token is not None:
        body["overrideMaxToken"] = args.max_token
    if args.top_p is not None:
        body["overrideTopP"] = args.top_p
    _put_json(config, f"/task/{args.task_id}/node/{args.node_id}/model", body)


def register_model(subparsers):
    model_parser = subparsers.add_parser("model", help="模型管理")
    model_sub = model_parser.add_subparsers(dest="action")

    # list
    p = model_sub.add_parser("list", help="查询可用模型列表")
    p.add_argument("--enabled", type=bool, help="是否启用过滤")
    p.add_argument("--model-name", help="模型名称过滤")

    # set-node
    p = model_sub.add_parser("set-node", help="修改节点模型配置")
    p.add_argument("--task-id", required=True, type=int, help="任务ID")
    p.add_argument("--node-id", required=True, help="节点ID")
    p.add_argument("--model-id", type=int, help="模型ID")
    p.add_argument("--temperature", type=float, help="温度")
    p.add_argument("--max-token", type=int, help="最大 Token 数")
    p.add_argument("--top-p", type=float, help="Top P")


MODEL_ACTIONS = {
    "list": model_list,
    "set-node": model_set_node,
}


# ============================== tag-base 子命令 ==============================

def tb_create(args, config):
    """创建标签库"""
    body = {"name": args.name, "type": args.type}
    if args.description:
        body["description"] = args.description
    if args.doc_info:
        body["docInfo"] = json.loads(args.doc_info)
    _post_json(config, "/tag-base/create", body)


def tb_update(args, config):
    """编辑标签库"""
    body = {"id": args.id}
    if args.name:
        body["name"] = args.name
    if args.description:
        body["description"] = args.description
    if args.doc_info:
        body["docInfo"] = json.loads(args.doc_info)
    _post_json(config, "/tag-base/update", body)


def tb_upload(args, config):
    """上传标签文件"""
    extra = {}
    if args.provider:
        extra["provider"] = args.provider
    _post_file(config, "/tag-base/upload-file", args.file, extra)


def tb_get(args, config):
    """标签库详情"""
    _get(config, f"/tag-base/{args.id}")


def tb_list(args, config):
    """标签库列表"""
    params = {"pageNum": args.page_num, "pageSize": args.page_size}
    if args.name:
        params["name"] = args.name
    if args.type:
        params["type"] = args.type
    if args.creator:
        params["creator"] = args.creator
    _get(config, "/tag-base/list", params)


def tb_retrieval_test(args, config):
    """召回测试"""
    body = {"id": args.id, "question": args.question}
    if args.top_k:
        body["topK"] = args.top_k
    _post_json(config, "/tag-base/retrieval/test", body)


def tb_delete(args, config):
    """删除标签库"""
    _delete(config, f"/tag-base/{args.id}")


def register_tag_base(subparsers):
    tb_parser = subparsers.add_parser("tag-base", help="标签库管理")
    tb_sub = tb_parser.add_subparsers(dest="action")

    # create
    p = tb_sub.add_parser("create", help="创建标签库")
    p.add_argument("--name", required=True, help="标签库名称")
    p.add_argument("--type", required=True, choices=["tag", "subject"], help="类型")
    p.add_argument("--description", help="描述")
    p.add_argument("--doc-info", help="文档信息 JSON（如 '[{\"fileId\":\"xxx\",\"fileName\":\"a.csv\"}]'）")

    # update
    p = tb_sub.add_parser("update", help="编辑标签库")
    p.add_argument("--id", required=True, type=int, help="标签库ID")
    p.add_argument("--name", help="新名称")
    p.add_argument("--description", help="新描述")
    p.add_argument("--doc-info", help="新文档信息 JSON")

    # upload
    p = tb_sub.add_parser("upload", help="上传标签文件")
    p.add_argument("--file", required=True, help="文件路径（CSV）")
    p.add_argument("--provider", help="知识库提供者")

    # get
    p = tb_sub.add_parser("get", help="标签库详情")
    p.add_argument("--id", required=True, type=int, help="标签库ID")

    # list
    p = tb_sub.add_parser("list", help="标签库列表")
    p.add_argument("--name", help="名称过滤")
    p.add_argument("--type", choices=["tag", "subject"], help="类型过滤")
    p.add_argument("--creator", help="创建人过滤")
    p.add_argument("--page-num", type=int, default=1, help="页码")
    p.add_argument("--page-size", type=int, default=10, help="每页条数")

    # retrieval-test
    p = tb_sub.add_parser("retrieval-test", help="召回测试")
    p.add_argument("--id", required=True, type=int, help="标签库ID")
    p.add_argument("--question", required=True, help="测试文本")
    p.add_argument("--top-k", type=int, help="返回条数上限")

    # delete
    p = tb_sub.add_parser("delete", help="删除标签库")
    p.add_argument("--id", required=True, type=int, help="标签库ID")


TB_ACTIONS = {
    "create": tb_create,
    "update": tb_update,
    "upload": tb_upload,
    "get": tb_get,
    "list": tb_list,
    "retrieval-test": tb_retrieval_test,
    "delete": tb_delete,
}


# ============================== 主入口 ==============================

COMMAND_MAP = {
    "task": TASK_ACTIONS,
    "prompt": PROMPT_ACTIONS,
    "error-case": EC_ACTIONS,
    "model": MODEL_ACTIONS,
    "tag-base": TB_ACTIONS,
}


def main():
    parser = argparse.ArgumentParser(
        description="Seederive CLI — 统一的 API 调用工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--base-url", help="API 基础地址（也可设 SEEDERIVE_BASE_URL 环境变量）")

    subparsers = parser.add_subparsers(dest="command")
    register_task(subparsers)
    register_prompt(subparsers)
    register_error_case(subparsers)
    register_model(subparsers)
    register_tag_base(subparsers)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    actions = COMMAND_MAP.get(args.command)
    if not actions:
        parser.print_help()
        sys.exit(1)

    if not args.action:
        # 打印子命令帮助
        parser.parse_args([args.command, "-h"])
        sys.exit(0)

    handler = actions.get(args.action)
    if not handler:
        print(f"错误：未知操作 '{args.command} {args.action}'", file=sys.stderr)
        sys.exit(1)

    config = get_config(args)
    handler(args, config)


if __name__ == "__main__":
    main()
