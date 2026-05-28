#!/usr/bin/env python3
"""
火山引擎托管 Prometheus (VMP) API 客户端
用于查询 Prometheus 指标数据
"""

from __future__ import print_function
import os
from typing import Optional

if __package__ in (None, ""):
    from _bootstrap import ensure_package

    ensure_package()
    from _byted_volcengine_vmp_scripts import config, models, sign  # type: ignore
else:
    from . import config, models, sign
import volcenginesdkcore


class VMPClient:
    """VMP API 客户端"""
    
    def __init__(
        self,
        ak: str = None,
        sk: str = None,
        region: str = "cn-beijing",
        endpoint: str = None,
        session_token: str = None,
    ):
        """
        初始化 VMP 客户端
        
        Args:
            ak: Access Key（可选，优先从环境变量或 .env 文件加载）
            sk: Secret Key（可选，优先从环境变量或 .env 文件加载）
            region: 区域（默认 cn-beijing）
            endpoint: 自定义域名（可选）
            session_token: 临时凭证 Token（可选）
        """
        self.conf = self._load_config(ak, sk, region, endpoint, session_token)
        self.service_code = "vmp"
        self.service_version = "2021-03-03"
        self.content_type_json = "application/json"
        self.content_type_form = "application/x-www-form-urlencoded"
    
    def _load_config(
        self,
        ak: str = None,
        sk: str = None,
        region: str = "cn-beijing",
        endpoint: str = None,
        session_token: str = None,
    ) -> config.VMPConfig:
        """加载配置"""
        # 先尝试从环境变量加载
        conf = config.load_env_config()
        
        # 如果提供了参数，覆盖环境变量
        if ak:
            conf.volcengine_ak = ak
        if sk:
            conf.volcengine_sk = sk
        if region:
            conf.volcengine_region = region
            if not conf.volcengine_endpoint:
                conf.volcengine_endpoint = f"vmp.{region}.volcengineapi.com"
        if endpoint:
            conf.volcengine_endpoint = endpoint
        if session_token:
            conf.session_token = session_token
        
        # 尝试从 .env 文件加载
        env_file = os.path.expanduser("~/.openclaw/workspace/.env")
        if os.path.exists(env_file):
            try:
                with open(env_file, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#") and "=" in line:
                            key, value = line.split("=", 1)
                            clean_value = value.strip().strip("\"'")
                            if key in ("VOLCENGINE_ACCESS_KEY", "VOLCENGINE_AK", "VOLC_ACCESSKEY") and not conf.volcengine_ak:
                                conf.volcengine_ak = clean_value
                            elif key in ("VOLCENGINE_SECRET_KEY", "VOLCENGINE_SK", "VOLC_SECRETKEY") and not conf.volcengine_sk:
                                conf.volcengine_sk = clean_value
                            elif key == "VOLCENGINE_REGION" and region == "cn-beijing":
                                conf.volcengine_region = clean_value or conf.volcengine_region
                            elif key == "VOLCENGINE_ENDPOINT" and not endpoint:
                                conf.volcengine_endpoint = clean_value
                            elif key == "VOLCENGINE_SESSION_TOKEN" and not session_token:
                                conf.session_token = clean_value
            except Exception as e:
                print(f"警告: 无法读取 .env 文件: {e}")

        if not conf.volcengine_endpoint:
            conf.volcengine_endpoint = f"vmp.{conf.volcengine_region}.volcengineapi.com"
        
        if not conf.is_valid():
            raise ValueError("未配置有效的 Access Key 和 Secret Key")
        
        return conf
    
    def query_instant_metrics(self, workspace_id: str, query: str, time: Optional[str] = None) -> dict:
        """
        即时查询 Metrics
        
        Args:
            workspace_id: 工作区 ID
            query: PromQL 查询语句
            time: 查询时间（可选，RFC3339 或 Unix 时间戳）
        
        Returns:
            查询结果
        """
        credentials = models.Credentials(
            access_key_id=self.conf.volcengine_ak,
            secret_access_key=self.conf.volcengine_sk,
            session_token=self.conf.session_token,
            region=self.conf.volcengine_region,
            service=self.service_code,
        )
        
        resp = sign.sign_and_request(
            volcenginesdkcore.UniversalInfo(
                method="POST",
                service=self.service_code,
                version=self.service_version,
                action="QueryMetrics",
                content_type=self.content_type_form,
            ),
            credentials,
            host=self.conf.volcengine_endpoint,
            query={
                'workspace': workspace_id,
            },
            header={
                "Content-Type": self.content_type_form,
            },
            body=models.QueryInstantMetricsRequest(
                query=query,
                time=time,
            ),
        )
        return resp
    
    def query_range_metrics(self, workspace_id: str, query: str, 
                          start: str, end: str, step: Optional[str] = None) -> dict:
        """
        范围查询 Metrics
        
        Args:
            workspace_id: 工作区 ID
            query: PromQL 查询语句
            start: 起始时间（RFC3339 或 Unix 时间戳）
            end: 结束时间（RFC3339 或 Unix 时间戳）
            step: 查询步长（可选，duration 格式，如 '15s'、'1m'、'1h'）
        
        Returns:
            查询结果
        """
        # 自动计算 step
        if step is None:
            step = self._calculate_default_step(start, end)
            print(f"自动计算 step: {step}")
        
        credentials = models.Credentials(
            access_key_id=self.conf.volcengine_ak,
            secret_access_key=self.conf.volcengine_sk,
            session_token=self.conf.session_token,
            region=self.conf.volcengine_region,
            service=self.service_code,
        )
        
        resp = sign.sign_and_request(
            volcenginesdkcore.UniversalInfo(
                method="POST",
                service=self.service_code,
                version=self.service_version,
                action="QueryMetricsRange",
                content_type=self.content_type_json,
            ),
            credentials,
            host=self.conf.volcengine_endpoint,
            query={
                'workspace': workspace_id,
            },
            header={
                # 范围查询 body 为 JSON
                "Content-Type": self.content_type_json,
            },
            body=models.QueryRangeMetricsRequest(
                workspace=workspace_id,
                query=query,
                start=start,
                end=end,
                step=step,
            ),
        )
        return resp
    
    def query_metric_names(self, workspace_id: str, match: Optional[str] = None) -> dict:
        """
        查询指标名称列表
        
        Args:
            workspace_id: 工作区 ID
            match: 匹配条件（可选，如 '{job=~"kubelet"}'）
        
        Returns:
            指标名称列表
        """
        credentials = models.Credentials(
            access_key_id=self.conf.volcengine_ak,
            secret_access_key=self.conf.volcengine_sk,
            session_token=self.conf.session_token,
            region=self.conf.volcengine_region,
            service=self.service_code,
        )
        
        match_list = [match] if match else None
        
        resp = sign.sign_and_request(
            volcenginesdkcore.UniversalInfo(
                method="POST",
                service=self.service_code,
                version=self.service_version,
                action="GetLabelValues",
                content_type=self.content_type_json,
            ),
            credentials,
            host=self.conf.volcengine_endpoint,
            query={
                'workspace': workspace_id,
                'label': '__name__',
            },
            header={
                "Content-Type": self.content_type_json,
            },
            body=models.GetLabelValuesRequest(
                workspace=workspace_id,
                label='__name__',
                matches=match_list,
            ),
        )
        return resp
    
    def query_metric_labels(self, workspace_id: str, metric_name: str) -> dict:
        """
        查询指标的标签列表
        
        Args:
            workspace_id: 工作区 ID
            metric_name: 指标名称
        
        Returns:
            标签列表
        """
        credentials = models.Credentials(
            access_key_id=self.conf.volcengine_ak,
            secret_access_key=self.conf.volcengine_sk,
            session_token=self.conf.session_token,
            region=self.conf.volcengine_region,
            service=self.service_code,
        )
        
        match_list = [metric_name] if metric_name else None
        
        resp = sign.sign_and_request(
            volcenginesdkcore.UniversalInfo(
                method="POST",
                service=self.service_code,
                version=self.service_version,
                action="GetLabels",
                content_type=self.content_type_json,
            ),
            credentials,
            host=self.conf.volcengine_endpoint,
            query={
                'workspace': workspace_id,
            },
            header={
                "Content-Type": self.content_type_json,
            },
            body=models.GetLabelsRequest(
                workspace=workspace_id,
                matches=match_list,
            ),
        )
        return resp

    def list_workspaces(self) -> dict:
        """
        查询 VMP 工作区列表

        说明：
        - 这部分能力使用官方 SDK（`volcenginesdkvmp`）实现，更稳定也更贴近控制台行为
        - SDK 缺失时返回结构化错误，避免脚本直接崩溃
        """
        try:
            import volcenginesdkvmp
            from volcenginesdkcore.rest import ApiException
        except Exception as exc:
            return {
                "error": "missing_dependency",
                "message": "缺少依赖 volcenginesdkvmp，请先安装 volcenginesdkvmp 或 volcengine-python-sdk",
                "detail": str(exc),
            }

        configuration = volcenginesdkcore.Configuration()
        configuration.ak = self.conf.volcengine_ak
        configuration.sk = self.conf.volcengine_sk
        configuration.region = self.conf.volcengine_region
        volcenginesdkcore.Configuration.set_default(configuration)

        api_instance = volcenginesdkvmp.VMPApi()
        req = volcenginesdkvmp.ListWorkspacesRequest()
        try:
            resp = api_instance.list_workspaces(req)
            return resp.to_dict() if hasattr(resp, "to_dict") else {"Result": resp}
        except ApiException as e:
            return {"error": "api_error", "message": str(e)}
    
    def query_series(self, workspace_id: str, match: str, 
                    start: Optional[str] = None, end: Optional[str] = None) -> dict:
        """
        查询时间序列
        
        Args:
            workspace_id: 工作区 ID
            match: 匹配条件（如 'up{job="node"}'）
            start: 起始时间（可选）
            end: 结束时间（可选）
        
        Returns:
            时间序列列表
        """
        credentials = models.Credentials(
            access_key_id=self.conf.volcengine_ak,
            secret_access_key=self.conf.volcengine_sk,
            session_token=self.conf.session_token,
            region=self.conf.volcengine_region,
            service=self.service_code,
        )
        
        match_list = [match] if match else None
        
        resp = sign.sign_and_request(
            volcenginesdkcore.UniversalInfo(
                method="POST",
                service=self.service_code,
                version=self.service_version,
                action="GetSeries",
                content_type=self.content_type_json,
            ),
            credentials,
            host=self.conf.volcengine_endpoint,
            query={
                'workspace': workspace_id,
            },
            header={
                "Content-Type": self.content_type_form,
            },
            body=models.GetSeriesRequest(
                workspace=workspace_id,
                matches=match_list,
                start=start,
                end=end,
            ),
        )
        return resp
    
    def _calculate_default_step(self, start: str, end: str) -> str:
        """
        计算默认的 step 值
        
        Args:
            start: 起始时间
            end: 结束时间
        
        Returns:
            step 值（秒数）
        """
        try:
            # 简单的计算逻辑
            import datetime
            
            def parse_time(time_str):
                if time_str.isdigit():
                    return float(time_str)
                # RFC3339/ISO8601：兼容 `Z` 结尾；无时区时默认按 UTC 处理
                normalized = time_str.replace("Z", "+00:00")
                dt = datetime.datetime.fromisoformat(normalized)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=datetime.timezone.utc)
                return dt.timestamp()
            
            start_time = parse_time(start)
            end_time = parse_time(end)
            
            duration_seconds = end_time - start_time
            if duration_seconds <= 0:
                return "5"
            
            step_seconds = int(duration_seconds / 100)
            step_seconds = max(step_seconds, 5)
            
            return f"{int(round(step_seconds))}"
        except Exception:
            return "5"
