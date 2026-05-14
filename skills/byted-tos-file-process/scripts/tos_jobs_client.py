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

import json
import os
import time
import urllib.request
import urllib.error
from typing import Optional

import tos


class TOSJobsClient:
    def __init__(self, ak: str, sk: str, endpoint: str, region: str, bucket: str):
        self.bucket = bucket
        self.region = region
        self.client = tos.TosClientV2(ak, sk, endpoint, region)

    def _signed_request(
        self, method: str, query: dict, body: Optional[bytes] = None
    ) -> dict:
        url_out = self.client.pre_signed_url(
            tos.HttpMethodType.Http_Method_Post
            if method == "POST"
            else tos.HttpMethodType.Http_Method_Get,
            self.bucket,
            "",
            expires=900,
            query=query,
        )
        req = urllib.request.Request(
            url_out.signed_url,
            data=body,
            method=method,
        )
        for k, v in url_out.signed_header.items():
            req.add_header(k, v)
        if body is not None:
            req.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(req) as resp:
                data = resp.read()
                return json.loads(data)
        except urllib.error.HTTPError as e:
            body_text = e.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"HTTP {e.code}: {body_text}") from e

    def create_job(self, job_category: str, job_type: str, job_detail: dict) -> dict:
        query = {job_category: "", "job_type": job_type}
        body = json.dumps(job_detail).encode("utf-8")
        return self._signed_request("POST", query, body)

    def get_job(
        self, job_type: str, job_id: str, job_category: str = "file_jobs"
    ) -> dict:
        query = {job_category: "", "job_type": job_type, "job_id": job_id}
        return self._signed_request("GET", query)

    def wait_for_job(
        self,
        job_type: str,
        job_id: str,
        timeout: int = 300,
        interval: int = 5,
        job_category: str = "file_jobs",
    ) -> dict:
        deadline = time.time() + timeout
        while time.time() < deadline:
            result = self.get_job(job_type, job_id, job_category=job_category)
            items = result.get("Items", [])
            if items:
                item = items[0]
            else:
                item = result
            state = item.get("State", "")
            if state in ("Success", "Failed"):
                return item
            time.sleep(interval)
        raise TimeoutError(f"Job {job_id} did not complete within {timeout}s")


def get_env(name: str) -> str:
    val = os.environ.get(name, "")
    if not val:
        raise ValueError(f"Environment variable {name} is required")
    return val


def create_client_from_env() -> TOSJobsClient:
    return TOSJobsClient(
        ak=get_env("TOS_ACCESS_KEY"),
        sk=get_env("TOS_SECRET_KEY"),
        endpoint=get_env("TOS_ENDPOINT"),
        region=get_env("TOS_REGION"),
        bucket=get_env("TOS_BUCKET"),
    )
