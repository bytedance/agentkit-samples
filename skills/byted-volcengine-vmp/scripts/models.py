from dataclasses import dataclass
from typing import List, Optional

from volcenginesdkcore.interceptor import RuntimeOption


@dataclass
class RequestBase:
    def __post_init__(self):
        self.build_swagger_types()
    
    def build_swagger_types(self):
        # 兼容 volcengine SDK 部分接口的参数描述结构（非强依赖）。
        self.swagger_types = {
            attr_name: type(attr_value).__name__
            for attr_name, attr_value in vars(self).items()
            if not attr_name.startswith("_") and not callable(attr_value)
        }
        self.attribute_map = {
            attr_name: attr_name
            for attr_name, attr_value in vars(self).items()
            if not attr_name.startswith("_") and not callable(attr_value)
        }

    def with_runtime_option(self, runtime_options: RuntimeOption):
        self._configuration = runtime_options
        return self

@dataclass
class ListWorkspacesRequest(RequestBase):
    PageNumber: int = 1
    PageSize: int = 100
    ShowAggregateQueryWorkspaces: bool = True

@dataclass
class QueryInstantMetricsRequest(RequestBase):
    query: str
    time: Optional[str] = None

@dataclass
class QueryRangeMetricsRequest(RequestBase):
    workspace: str
    query: str
    start: str
    end: str
    step: Optional[str] = None
       
@dataclass
class GetLabelValuesRequest(RequestBase):
    workspace: str
    label: str
    start: Optional[str] = None
    end: Optional[str] = None
    matches: Optional[List[str]] = None
    limit: Optional[int] = None

@dataclass
class GetLabelsRequest(RequestBase):
    workspace: str
    start: Optional[str] = None
    end: Optional[str] = None
    matches: Optional[List[str]] = None
    limit: Optional[int] = None

@dataclass
class GetSeriesRequest(RequestBase):
    workspace: str
    matches: Optional[List[str]]
    start: Optional[str] = None
    end: Optional[str] = None
    limit: Optional[int] = None

@dataclass
class Credentials:
    access_key_id: str
    secret_access_key: str
    region: str
    service: str
    session_token: Optional[str] = None
