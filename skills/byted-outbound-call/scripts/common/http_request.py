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
from typing import Dict, Any

import requests
import json
import os
import sys

from .logger_config import get_file_logger, get_console_logger
from .http_headers import build_headers

# 添加scripts目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import volc.volc_openai as volc_openai

file_logger = get_file_logger("http_request")
LOCAL_API_BASE_URL = "http://localhost:8000"
LOCAL_DEBUG = False

def run_submit_job(submit_job_request) -> Dict[str, Any]:
    file_logger.info("准备调用 SubmitJob 接口")
    file_logger.info("RequestBody: %s", json.dumps(submit_job_request.__dict__, ensure_ascii=False))

    if LOCAL_DEBUG:
        return _run_submit_job_local(submit_job_request)

    headers = buildBytebotVoclHeaders()

    response_body = volc_openai.request("POST", "SubmitJob", json.dumps(submit_job_request.__dict__), headers)
    return response_body


def _run_submit_job_local(submit_job_request) -> Dict[str, Any]:
    url = f"{LOCAL_API_BASE_URL}?Action=SubmitJob"

    headers = build_headers()

    file_logger.info("URL: %s", url)
    file_logger.info("Headers: %s", json.dumps(headers, ensure_ascii=False))

    response = requests.post(url, headers=headers, json=submit_job_request.__dict__, timeout=10)
    response.raise_for_status()

    return response.json()


def query_job_status(job_id: str) -> Dict[str, Any]:
    file_logger.info("准备调用 QueryJobStatus，JobId=%s", job_id)
    file_logger.info("RequestBody: %s", job_id)

    if LOCAL_DEBUG:
        return _query_job_status_local(job_id)

    headers = buildBytebotVoclHeaders()
    body = f'{{"JobId":"{job_id}"}}'

    response_body = volc_openai.request("POST", "QueryJobStatus", body, headers)
    return response_body


def _query_job_status_local(job_id: str) -> Dict[str, Any]:
    url = f"{LOCAL_API_BASE_URL}?Action=QueryJobStatus"
    headers = build_headers()
    payload = {"JobId": job_id}

    file_logger.info("URL: %s", url)
    file_logger.info("Headers: %s", json.dumps(headers, ensure_ascii=False))

    response = requests.post(url, headers=headers, json=payload, timeout=10)
    response.raise_for_status()
    return response.json()


def query_job_detail(job_id: str,) -> Dict[str, Any]:
    file_logger.info("准备调用 QueryJobDetail，JobId=%s", job_id)
    file_logger.info("RequestBody: %s", job_id)

    if LOCAL_DEBUG:
        return _query_job_detail_local(job_id)

    headers = buildBytebotVoclHeaders()
    body = f'{{"JobId":"{job_id}"}}'

    response_body = volc_openai.request("POST", "QueryJobDetail", body, headers)
    return response_body


def _query_job_detail_local(
        job_id: str,
) -> Dict[str, Any]:
    """调用 QueryJobDetail 接口。"""
    url = f"{LOCAL_API_BASE_URL}?Action=QueryJobDetail"
    headers = build_headers()
    payload = {"JobId": job_id}

    file_logger.info("URL: %s", url)
    file_logger.info("Headers: %s", json.dumps(headers, ensure_ascii=False))

    response = requests.post(url, headers=headers, json=payload, timeout=10)
    response.raise_for_status()
    return response.json()


def buildBytebotVoclHeaders() -> Dict[str, str]:
    headers = build_headers()
    # headers['x-use-ppe'] = '1'
    # headers['X-TT-ENV'] = 'ppe_volcengine'
    ppe_env = os.environ.get("ppe_env")
    if ppe_env:
        headers['X-VOLC-ENV'] = ppe_env
    return headers
