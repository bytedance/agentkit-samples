import os
import json
import urllib.request
import urllib.parse
from typing import Any, Dict
from api import MilvusApi, VpcApi, ApiError

api_host = os.environ.get("ARK_SKILL_API_BASE")
api_key = os.environ.get("ARK_SKILL_API_KEY")

def check_is_ark_env() -> bool:
    return api_host and api_key

def make_direct_http_call(service_name: str, action: str, version: str, method: str, body_dict: Dict[str, Any] = None) -> Dict:
    if not check_is_ark_env():
        raise ApiError("ARK_SKILL_API_BASE and ARK_SKILL_API_KEY environment variables must be set for arkclaw_shim")
        
    url = f"{api_host.rstrip('/')}/?Action={action}&Version={version}"
    headers = {
        "ServiceName": service_name,
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json"
    }

    if method.upper() == "GET":
        if body_dict:
            query = urllib.parse.urlencode(body_dict, doseq=True)
            url = f"{url}&{query}"
        data = None
    else:
        headers["Content-Type"] = "application/json"
        data = json.dumps(body_dict).encode("utf-8") if body_dict else b""
        
    req = urllib.request.Request(url, data=data, headers=headers, method=method.upper())

    try:
        with urllib.request.urlopen(req) as resp:
            resp_body = resp.read().decode('utf-8')
            return json.loads(resp_body)
    except urllib.error.HTTPError as e:
        error_body = e.read().decode('utf-8')
        raise ApiError(f"HTTP {e.code}: {e.reason} - {error_body}")
    except Exception as e:
        raise ApiError(f"Network error: {str(e)}")

class MilvusHttpShim(MilvusApi):
    def _call(self, method: str, action: str, body: Any) -> Any:
        return make_direct_http_call("milvus", action, "2023-01-01", method, body)

class VpcHttpShim(VpcApi):
    def _call(self, method: str, action: str, body: Any) -> Any:
        return make_direct_http_call("vpc", action, "2020-04-01", method, body)

def get_clients():
    region = os.environ.get("VOLCENGINE_REGION", "cn-beijing")
    return MilvusHttpShim(), VpcHttpShim(), region
