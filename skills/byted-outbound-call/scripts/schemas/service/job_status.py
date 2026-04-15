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
from enum import IntEnum, unique

@unique  # 确保枚举值唯一，避免重复定义
class JobStatus(IntEnum):
    """
    呼叫任务(Job)状态枚举

    枚举值对应含义和说明：
    1: Waiting - 呼叫任务已提交，正在排队等待系统发起呼叫。
    2: Running - 呼叫任务正在处理中，如商家未接听，系统会自动重呼，请耐心等待。
    3: CallFinished - 所有预定的呼叫（包括重呼）均已执行完毕，正在分析通话结果。
    4: JobFinished -已完成预订的呼叫，并且完成通话结果分析。。
    5: NoExist - 呼叫任务不存在
    """
    # 定义枚举成员（值: 名称）
    Waiting = 1
    Running = 2
    CallFinished = 3
    JobFinished = 4
    NoExist = 5

    @classmethod
    def get_job_status_description(cls, value):
        """
        根据枚举值获取对应的详细说明
        :param value: 枚举数值（1-5）
        :return: 对应的说明文本，若不存在返回 None
        """
        desc_map = {
            cls.Waiting: "Job 已提交，正在排队等待系统发起呼叫。",
            cls.Running: "呼叫任务正在处理中，如商家未接听，系统会自动重呼，请耐心等待。",
            cls.CallFinished: "所有预定的呼叫（包括重呼）均已执行完毕，正在分析通话结果。",
            cls.JobFinished: "已完成预订的呼叫，并且完成通话结果分析。",
            cls.NoExist: "呼叫任务不存在"
        }
        return desc_map.get(cls(value), None)
