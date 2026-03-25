import os
import sys
import json
from typing import Any
from api import MilvusApi, VpcApi, ApiError

class UniversalSdkShim:
    def __init__(self):
        import volcenginesdkcore
        from volcenginesdkcore.universal import UniversalApi
        
        ak = os.environ.get("VOLCENGINE_ACCESS_KEY")
        sk = os.environ.get("VOLCENGINE_SECRET_KEY")
        region = os.environ.get("VOLCENGINE_REGION", "cn-beijing")

        if not ak or not sk:
            raise ApiError("Missing Credentials: VOLCENGINE_ACCESS_KEY or VOLCENGINE_SECRET_KEY are not set.")

        configuration = volcenginesdkcore.Configuration()
        configuration.ak = ak
        configuration.sk = sk
        configuration.region = region
        configuration.client_side_validation = False

        self.client = volcenginesdkcore.ApiClient(configuration)
        self.uapi = UniversalApi(self.client)

    def _call_universal(self, service: str, action: str, version: str, method: str, body: Any) -> Any:
        from volcenginesdkcore.universal import UniversalInfo
        from volcenginesdkcore.rest import ApiException
        
        info = UniversalInfo(method=method, service=service, version=version, action=action)
        if method.upper() == "POST":
            info.content_type = "application/json"
            
        try:
            return self.uapi.do_call(info, body)
        except ApiException as e:
            raise ApiError(str(e))
        except Exception as e:
            raise ApiError(f"SDK Error: {str(e)}")

class MilvusSdkShim(MilvusApi):
    def __init__(self, bridge: UniversalSdkShim):
        self._bridge = bridge

    def _call(self, method: str, action: str, body: Any) -> Any:
        return self._bridge._call_universal("milvus", action, "2023-01-01", method, body)

class VpcSdkShim(VpcApi):
    def __init__(self, bridge: UniversalSdkShim):
        self._bridge = bridge

    def _call(self, method: str, action: str, body: Any) -> Any:
        return self._bridge._call_universal("vpc", action, "2020-04-01", method, body)

def get_clients():
    try:
        bridge = UniversalSdkShim()
        region = os.environ.get("VOLCENGINE_REGION", "cn-beijing")
        return MilvusSdkShim(bridge), VpcSdkShim(bridge), region
    except ApiError as e:
        print(json.dumps({
            "error": "Initialization Error", 
            "details": str(e)
        }))
        sys.exit(1)
