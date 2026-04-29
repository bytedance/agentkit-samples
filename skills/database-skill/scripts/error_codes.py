"""dbw-mgr OpenAPI 错误码映射。

dbw-mgr 在 MR 5292 统一了 SLO 错误码（见 `biz/handler/openapi/validation_and_errorwrap.go`），
响应结构示例：`ResponseMetadata.Error = {"CodeN": 1xxxxx, "Code": "InstanceIdParamError", "Message": "..."}`。

本模块定义：
1. `DbwApiError`：承载结构化错误信息的异常类（含 ConnectionFailed 的 subtype 解析）。
2. `ERROR_CODE_HINTS`：错误码 → 中文友好提示 + 修复建议。
3. `CONNECTION_FAILED_SUBTYPE_HINTS`：ConnectionFailed 按 subtype 展开的精准修复建议。
4. `format_error_message`：将 Code/Message/RequestId/Hint 拼成最终消息。
"""

import re
from typing import Optional


# ConnectionFailed 子类从 dbw-mgr MR 5292 的 validation_and_errorwrap.go::connectionSubType() 定义。
# Message 形如: "op=execute sql fail reason=connection.auth: access denied for user ..."
# ─── 向后兼容 ───
# 老版本 dbw-mgr（MR 5292 合并前）返回的 ConnectionFailed 不带 reason=connection.<subtype> 前缀，
# 或根本不返回 ConnectionFailed（走 SystemError/CustomErr 兜底）。本模块的处理：
#   1) 正则匹配不到 → self.subtype="" → hint 回退到 ConnectionFailed 通用文案
#   2) code 是老版本返回的未知码（如 CustomErr）→ hint 空，但 code/message/request_id 照常结构化
# 无论 dbw-mgr 版本如何，DbwApiError 都不会崩，仅 hint 精度会降级。
_CONN_SUBTYPE_RE = re.compile(r"reason=connection\.(\w+)")

# ConnectionFailed 子类对应的精准 hint（MR 5292 之后可用）
CONNECTION_FAILED_SUBTYPE_HINTS: dict[str, str] = {
    "auth": (
        "账密错误导致连接失败。请：①在 DBW 控制台确认实例管理员 / 数据库账号密码；"
        "②若是临时凭据，检查是否已过期；③确认连接使用的用户名与目标库有访问权限。"
    ),
    "db_not_found": (
        "指定的数据库不存在。请：①用 list_databases() 列出可用库并对照；"
        "②确认传入的 database 参数拼写正确（区分大小写）；③确认该库未被删除或重命名。"
    ),
    "host_unreachable": (
        "数据库实例不可达。请：①确认实例状态为 Running（list_instances 查看）；"
        "②检查是否在实例白名单内；③确认 VPC / 网络链路连通。"
    ),
    "ssl": (
        "TLS/SSL 握手失败。请：①确认客户端和服务端 TLS 版本一致；②证书链是否有效、未过期；"
        "③是否需要指定 CA 证书路径。"
    ),
    "unknown": (
        "连接失败但驱动未返回具体子类。建议查看原始 Message 中的驱动报错字段，"
        "或直接在 DBW 控制台测试实例连通性。"
    ),
}


class DbwApiError(Exception):
    """dbw-mgr OpenAPI 结构化错误。

    对 `ConnectionFailed` 自动解析 Message 中的 `reason=connection.<subtype>` 字段，
    暴露为 `self.subtype`，并选用 subtype 对应的精准 hint。

    向后兼容：老版本 dbw-mgr 未带 subtype 前缀或返回其他错误码时，subtype 为空字符串，
    hint 回退到通用 ERROR_CODE_HINTS（未知码时为 ""），不影响 code/message/request_id。
    """

    def __init__(self, code: str, message: str, request_id: str = "", code_n: Optional[int] = None):
        self.code = code or ""
        self.message = message or ""
        self.request_id = request_id or ""
        self.code_n = code_n
        self.subtype = ""

        if self.code == "ConnectionFailed":
            m = _CONN_SUBTYPE_RE.search(self.message)
            if m:
                self.subtype = m.group(1)
            # MR 5292 前：无 subtype 前缀 → 回退到通用 ConnectionFailed hint
            self.hint = (
                CONNECTION_FAILED_SUBTYPE_HINTS.get(self.subtype)
                or ERROR_CODE_HINTS.get(self.code, "")
            )
        else:
            # 未在 ERROR_CODE_HINTS 的老版本错误码 → hint 为空，code/message 仍结构化
            self.hint = ERROR_CODE_HINTS.get(self.code, "")

        super().__init__(format_error_message(self.code, self.message, self.request_id, self.hint))


ERROR_CODE_HINTS: dict[str, str] = {
    # 高价值（execute_sql / list_* / 所有 API 通用）
    "InstanceIdParamError": "缺少或不合法的 InstanceId。请在调用前显式传入 instance_id，或检查 client 配置。",
    "InstanceTypeParamError": (
        "InstanceType 在 InstanceId 存在时必填且需合法（MySQL/Postgres/Mongo/Redis/MSSQL/VeDBMySQL/External）。"
        "client.get_instance_type(instance_id) 会自动解析；若解析失败请确认实例是否存在、region 是否正确。"
    ),
    "QueryTimeRangeError": "时间范围不合法。StartTime 必填，且 StartTime~EndTime 间隔不能超过 31 天。",
    "PaginationParamError": "分页参数越界。PageNumber 必须 ≥1，PageSize 必须在 1~100 之间。",
    "CallThirdPartyTimeout": (
        "下游服务/SQL 执行超时。对 execute_sql 常见诱因：①大表全表扫；②缺索引；③数据源负载高。"
        "建议：加 WHERE 条件 / LIMIT、用 EXPLAIN 检查执行计划、或分页查询。"
    ),
    "ConnectionFailed": (
        "连接数据源失败。Message 中 reason=connection.<subtype> 会进一步标识子类。"
        "DbwApiError.subtype 已自动解析：auth / db_not_found / host_unreachable / ssl / unknown。"
    ),
    "ExternalNetworkUnreachable": "网络不可达。请检查实例所在 VPC/白名单配置，或通过控制台 telnet 连通性。",
    "InvalidAccessKey": "AccessKey 无效。请检查 VOLCENGINE_ACCESS_KEY / VOLCENGINE_SECRET_KEY 是否正确。",
    # 中等价值
    "InputParamError": "入参校验未通过（req.IsValid() 失败）。请检查必填字段、枚举值是否符合接口定义。",
    "ObjectNameParamError": "缺少对象名参数（如 database/table）。请补齐后再调用。",
    "TaskIdParamError": "缺少或不合法的 TaskId/TicketId。数组参数不能为空且元素数量应 ≤100。",
    "CreateSessionError": "创建会话失败。通常为权限不足或实例不可用：确认实例状态为 Running，且账号已在 DBW 控制台授权。",
    "ParamError": "通用参数错误。请对照接口定义检查每个字段的取值范围与枚举合法性。",
    # 低频（toolbox 未封装对应 API，保留兜底）
    "TenantNotFound": "当前账号所在租户未找到。请联系管理员确认租户开通状态。",
    "RecordNotFound": "目标记录不存在。请确认 ticket_id/instance_id 等资源标识是否正确，或是否已被删除。",
    "ManualExecuteTicketError": "工单人工执行失败。请查看工单详情中的错误信息，或检查工单状态是否允许人工执行。",
    # 终极兜底
    "SystemError": "服务端兜底错误。Message 中包含原始错误信息，可据此定位根因；如持续出现请联系管理员。",
    "CustomAbnormal": "服务端异常（老版本 dbw-mgr 兜底码）。Message 中 `status=<真实码> msg=<原始错误>` 含实际原因。",
}


def format_error_message(code: str, message: str, request_id: str = "", hint: str = "") -> str:
    parts = []
    if code:
        parts.append(f"[{code}]")
    if message:
        parts.append(message)
    prefix = " ".join(parts) if parts else "Unknown API error"
    tail = []
    if hint:
        tail.append(f"💡 {hint}")
    if request_id:
        tail.append(f"(RequestId: {request_id})")
    if tail:
        return prefix + "\n" + "\n".join(tail)
    return prefix
