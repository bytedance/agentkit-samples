import json
import urllib.request
import urllib.error
import re
import os
from typing import Any, Dict, Optional


class DBWClient:
    def __init__(
        self,
        region: Optional[str] = None,
        instance_id: Optional[str] = None,
        instance_type: Optional[str] = None,
        database: Optional[str] = None,
        api_url: Optional[str] = None,
        api_key: Optional[str] = None,
        ve_tip_token: Optional[str] = None,
    ):
        self.region = region or os.environ.get("VOLCENGINE_REGION")
        self.instance_id = instance_id or os.environ.get("VOLCENGINE_INSTANCE_ID")
        self.instance_type = instance_type or os.environ.get("VOLCENGINE_INSTANCE_TYPE")
        self.database = database or os.environ.get("VOLCENGINE_DATABASE")

        self.api_url = api_url or os.environ.get("DATABASE_VIKING_APIG_URL")
        self.api_key = api_key or os.environ.get("DATABASE_VIKING_APIG_KEY")
        self.ve_tip_token = ve_tip_token or os.environ.get("VE_TIP_TOKEN")
        
        if not self.api_url or not self.api_key:
            raise ValueError("缺少环境变量: DATABASE_VIKING_APIG_URL 或 DATABASE_VIKING_APIG_KEY")
        if not self.ve_tip_token:
            raise ValueError("缺少环境变量: VE_TIP_TOKEN")


    def _convert_pascal_to_snake(self, data: Any) -> Any:
        if not isinstance(data, dict):
            if isinstance(data, list):
                return [self._convert_pascal_to_snake(item) for item in data]
            return data
        converted = {}
        for key, value in data.items():
            snake_key = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", key)
            snake_key = re.sub(r"([a-z])([A-Z])", r"\1_\2", snake_key)
            snake_key = snake_key.lower()
            converted[snake_key] = self._convert_pascal_to_snake(value)
        return converted

    def _call_api(self, action: str, body_args: Dict[str, Any]) -> Dict[str, Any]:
        api_url = self.api_url.rstrip("/")
        if api_url.startswith(("http://", "https://")):
            base_url = api_url
        else:
            base_url = f"https://{api_url}"
        url = f"{base_url}?Action={action}&Version=2018-01-01"

        body_dict = {}
        for k, v in body_args.items():
            if v is None:
                continue
            if k[0].isupper() and "_" not in k:
                body_dict[k] = v
            else:
                body_dict[self._pascal_case(k)] = v

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
            "ServiceName": "dbw",
            "X-Volc-Dbw-Skill": "database-toolbox-ai-search-agentkit",
            "x-ve-tip-token": self.ve_tip_token
        }

        req = urllib.request.Request(url, data=json.dumps(body_dict).encode("utf-8"), headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                result = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            error_body = e.read().decode("utf-8")
            raise ValueError(f"HTTP {e.code}: {error_body}")

        if "ResponseMetadata" in result:
            meta = result["ResponseMetadata"]
            request_id = meta.get("RequestId", "Unknown")
            if meta.get("Error"):
                raise ValueError(f"API Error: {meta['Error']} (RequestId: {request_id})")

        if "Result" in result:
            res = result["Result"]
            if isinstance(res, dict):
                if "Results" in res:
                    return res
                return self._convert_pascal_to_snake(res)
            return res
        elif "ResponseMetadata" in result:
            meta = result["ResponseMetadata"]
            if meta.get("Error"):
                raise ValueError(f"API Error: {meta['Error']}")

        return result

    def _pascal_case(self, s: str) -> str:
        components = s.split("_")
        return "".join(x.title() for x in components)

    def nl2sql(self, args: Dict[str, Any]) -> Dict[str, Any]:
        return self._call_api("GenerateSQLFromNL", args)

    def execute_sql(self, args: Dict[str, Any]) -> Dict[str, Any]:
        result = self._call_api("ExecuteSQL", args)
        if isinstance(result, dict):
            if "Results" in result or "results" in result:
                return result
        return result

    def list_databases(self, args: Dict[str, Any]) -> Dict[str, Any]:
        return self._call_api("ListDatabases", args)

    def list_tables(self, args: Dict[str, Any]) -> Dict[str, Any]:
        return self._call_api("ListTables", args)

    def get_table_info(self, args: Dict[str, Any]) -> Dict[str, Any]:
        return self._call_api("GetTableInfo", args)

    def describe_instance_management(self, args: Dict[str, Any]) -> Dict[str, Any]:
        return self._call_api("DescribeInstanceManagement", args)
