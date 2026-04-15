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
class CallResult(IntEnum):
    """
    呼叫任务(Job)状态枚举

    枚举值对应含义和说明：
    1: Waiting - 等待呼叫。Job 已提交，正在排队等待系统发起呼叫。
    2: Running - 呼叫中或等待重呼。系统正在进行呼叫，或者当前轮次呼叫失败后，正在等待下一个重呼周期的到来。
    3: CallFinished - 呼叫结束。所有预定的呼叫（包括重呼）均已执行完毕，但 Job 的最终数据仍在处理中。
    4: JobFinished - Job 结束。Job 已彻底完成，此时可以通过 QueryJobDetail 接口查询到完整的呼叫结果，如通话详情、定级信息等。
    5: NoExist - Job不存在
    """
    # 定义枚举成员（值: 名称）
    Connected = 1
    Shutdown = 2
    OutOfService = 3
    NotFound = 4
    ConnectionFailed = 6
    NoAnswer = 7
    Busy = 8
    NotConnected = 2000
    

    @classmethod
    def get_call_result_description(cls, value):
        """
        根据枚举值获取对应的详细说明
        :param value: 枚举数值（1-5）
        :return: 对应的说明文本，若不存在返回 None
        """
        desc_map = {
            cls.Connected: "正常接通",
            cls.Shutdown: "关机",
            cls.OutOfService: "停机",
            cls.NotFound: "空号",
            cls.ConnectionFailed: "暂时无法接通",
            cls.NoAnswer: "无人接听",
            cls.Busy: "被叫忙",
            cls.NotConnected: "未接通",
        }
        return desc_map.get(cls(value), None)
