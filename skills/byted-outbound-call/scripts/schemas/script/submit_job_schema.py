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


class SubmitJobParams:
    """外呼任务参数实体类"""
    
    def __init__(self, user_phone_number: str, shop_phone_number: str, first_name: str,
                 date: str = "", time: str = "", people_number: str = "", shop_name: str = "",
                 new_date: str = "", new_time: str = "", new_people_number: str = ""):
        """
        初始化外呼任务参数对象
        
        Args:
            user_phone_number: 用户联系电话（所有场景必填）
            shop_phone_number: 门店电话（所有场景必填）
            first_name: 用户姓氏（所有场景必填）
            date: 预约日期（仅预约场景）
            time: 预约时间（仅预约场景）
            people_number: 预约人数（仅预约场景）
            shop_name: 门店名称（所有场景必填）
            new_date: 新预约日期（仅改订场景）
            new_time: 新预约时间（仅改订场景）
            new_people_number: 新预约人数（仅改订场景）
        """
        self.user_phone_number = user_phone_number
        self.shop_phone_number = shop_phone_number
        self.first_name = first_name
        self.date = date
        self.time = time
        self.people_number = people_number
        self.new_date = new_date
        self.new_time = new_time
        self.new_people_number = new_people_number
        self.shop_name = shop_name


class SubmitJobOuter:
    """
    外呼任务数据模型类
    对应JSON结构：
    {
     "job_name": "【预约/改订/取消】+ 门店名称 + 用户需求",
     "job_description": "用户自然语言原始需求（可选）",
     "script_id": "对应场景的剧本ID",
     "params": {
      "user_phone_number": "联系电话（所有场景必填）",
      "date": "预约日期（仅预约场景）",
      "time": "预约时间（仅预约场景）",
      "people_number": "预约人数（仅预约场景）",
      "shop_phone_number": "门店电话（所有场景必填）",
      "first_name": "用户姓氏（所有场景必填）",
      "new_date": "新预约日期（仅改订场景）",
      "new_time": "新预约时间（仅改订场景）",
      "new_people_number": "新预约人数（仅改订场景）",
      "shop_name": "门店名称（所有场景必填）"
     }
    }
    """

    def __init__(self, job_name: str, script_id: str, params: SubmitJobParams, 
                 job_description: str = ""):
        """
        初始化外呼任务对象

        Args:
            job_name: 任务名称，格式为"【预约/改订/取消】+ 门店名称 + 用户需求"
            script_id: 剧本ID
            params: 参数实体对象
            job_description: 用户自然语言原始需求（可选）
        """
        self.job_name = job_name
        self.job_description = job_description
        self.script_id = script_id
        self.params = params

    def to_dict(self) -> dict:
        """
        将对象转换为字典格式

        Returns:
            dict: 包含所有字段的字典
        """
        return {
            "job_name": self.job_name,
            "job_description": self.job_description,
            "script_id": self.script_id,
            "params": {
                "user_phone_number": self.params.user_phone_number,
                "shop_phone_number": self.params.shop_phone_number,
                "first_name": self.params.first_name,
                "date": self.params.date,
                "time": self.params.time,
                "people_number": self.params.people_number,
                "shop_name": self.params.shop_name,
                "new_date": self.params.new_date,
                "new_time": self.params.new_time,
                "new_people_number": self.params.new_people_number
            }
        }

    @classmethod
    def from_json(cls, json_str: str) -> 'SubmitJobOuter':
        """
        从JSON字符串创建OutboundJob对象

        Args:
            json_str: 包含外呼任务数据的JSON字符串

        Returns:
            SubmitJobOuter: 创建的OutboundJob对象
        """
        data = json.loads(json_str)
        return cls.from_dict(data)

    @classmethod
    def from_dict(cls, data: dict) -> 'SubmitJobOuter':
        """
        从字典创建OutboundJob对象

        Args:
            data: 包含外呼任务数据的字典

        Returns:
            SubmitJobOuter: 创建的OutboundJob对象
        """
        params_data = data.get('params', {})
        params = SubmitJobParams(
            user_phone_number=params_data.get('user_phone_number', ''),
            shop_phone_number=params_data.get('shop_phone_number', ''),
            first_name=params_data.get('first_name', ''),
            date=params_data.get('date', ''),
            time=params_data.get('time', ''),
            people_number=params_data.get('people_number', ''),
            new_date=params_data.get('new_date', ''),
            new_time=params_data.get('new_time', ''),
            shop_name=params_data.get('shop_name', ''),
            new_people_number=params_data.get('new_people_number', '')
        )
        
        return cls(
            job_name=data.get('job_name', ''),
            job_description=data.get('job_description', ''),
            script_id=data.get('script_id', ''),
            params=params
        )

    def validate(self) -> tuple[bool, str]:
        """
        验证必填字段是否完整

        Returns:
            tuple[bool, str]: (是否验证通过, 错误信息)
        """
        if not self.job_name:
            return False, "任务名称不能为空"
        if not self.script_id:
            return False, "剧本ID不能为空"
        if not self.params.user_phone_number:
            return False, "用户联系电话不能为空"
        if not self.params.shop_phone_number:
            return False, "门店电话不能为空"
        if not self.params.first_name:
            return False, "用户姓氏不能为空"
        if not self.params.shop_name:
            return False, "门店名称不能为空"

        # 根据剧本ID验证场景特定字段
        if self.script_id == ScriptType.RESERVATION:  # 预约场景
            if not self.params.date:
                return False, "预约场景必须提供预约日期"
            if not self.params.time:
                return False, "预约场景必须提供预约时间"
            if not self.params.people_number:
                return False, "预约场景必须提供预约人数"

        elif self.script_id == ScriptType.MODIFICATION:  # 改订场景
            if not self.params.new_date:
                return False, "改订场景必须提供新预约日期"
            if not self.params.new_time:
                return False, "改订场景必须提供新预约时间"
            if not self.params.new_people_number:
                return False, "改订场景必须提供新预约人数"

        return True, "验证通过"

    def __str__(self) -> str:
        """返回对象的字符串表示"""
        return f"SubmitJobOuter(job_name='{self.job_name}', script_id='{self.script_id}')"

    def __repr__(self) -> str:
        """返回对象的详细字符串表示"""
        return (f"SubmitJobOuter(job_name='{self.job_name}', "
                f"job_description='{self.job_description}', "
                f"script_id='{self.script_id}', "
                f"params={self.params})")


# 场景常量定义
class ScriptType:
    """剧本类型常量"""
    RESERVATION = "llm_wlne_biffj"  # 预约
    MODIFICATION = "llm_eeac_bigci"  # 改订
    CANCELLATION = "llm_ivqy_bigcj"  # 取消