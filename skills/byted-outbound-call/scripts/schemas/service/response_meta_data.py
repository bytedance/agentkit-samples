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
class Error:
    """错误信息类"""

    def __init__(self, Code: str, Message: str):
        """
        初始化错误信息

        Args:
            Code: 错误码
            Message: 错误描述
        """
        self.Code = Code
        self.Message = Message


class ResponseMetadata:
    """响应元数据类"""

    def __init__(self, RequestId: str, Action: str, Version: str, Service: str, Region: str, Error: Error = None):
        """
        初始化响应元数据

        Args:
            RequestId: 请求ID
            Action: 操作名称
            Version: API版本
            Service: 服务名称
            Region: 区域
            Error: 错误信息
        """
        self.RequestId = RequestId
        self.Action = Action
        self.Version = Version
        self.Service = Service
        self.Region = Region
        self.Error = Error

    @classmethod
    def from_dict(cls, param):
        """
        从dict创建ResponseMetadata对象
        Args:
            param: 包含响应元数据的dict

        Returns:
            ResponseMetadata对象
        """
        return cls(
            RequestId=param["RequestId"],
            Action=param["Action"],
            Version=param["Version"],
            Service=param["Service"],
            Region=param["Region"],
            Error=Error(param["Error"]["Code"], param["Error"]["Message"]) if "Error" in param else None
        )
