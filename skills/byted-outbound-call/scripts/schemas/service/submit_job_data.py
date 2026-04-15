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
from .response_meta_data import ResponseMetadata

class SubmitJobRequest:
    """提交外呼任务请求类"""
    
    def __init__(self, Phone: str, ScriptName: str, VariableParams: dict):
        """
        初始化提交任务请求
        
        Args:
            Phone: 电话号码
            ScriptName: 剧本名称
            VariableParams: 变量参数字典，包含用户自定义参数
        """
        self.Phone = Phone
        self.ScriptName = ScriptName
        self.VariableParams = VariableParams


class SubmitJobResult:
    """提交任务结果类"""
    
    def __init__(self, JobId: str):
        """
        初始化提交任务结果
        
        Args:
            JobId: 任务ID
        """
        self.JobId = JobId


class SubmitJobResponse:
    """提交外呼任务响应类"""
    
    def __init__(self, ResponseMetadata: ResponseMetadata, Result: SubmitJobResult):
        """
        初始化提交任务响应
        
        Args:
            ResponseMetadata: 响应元数据
            Result: 任务结果
        """
        self.ResponseMetadata = ResponseMetadata
        self.Result = Result

    @classmethod
    def from_dict(cls, response_body: dict) -> 'SubmitJobResponse':
        """
        从dict创建SubmitJobResponse对象

        Args:
            response_body: JSON格式的响应字符串

        Returns:
            SubmitJobResponse对象
        """
        # 创建ResponseMetadata对象
        response_metadata = ResponseMetadata.from_dict(response_body["ResponseMetadata"])
        # 创建SubmitJobResult对象
        result = SubmitJobResult(response_body["Result"]["JobId"])
        # 返回SubmitJobResponse对象
        return cls(response_metadata, result)
