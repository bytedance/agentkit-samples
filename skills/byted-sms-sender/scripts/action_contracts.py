# Copyright (c) 2026 Beijing Volcano Engine Technology Co., Ltd. and/or its affiliates.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
"""Machine-readable contracts for every public SMS Action used by the Skill."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, Optional, Set


SMS_API_VERSION = "2026-01-01"
LIVE_VALIDATION_ACTIONS = frozenset(
    {
        "ListSubAccountForAgent",
        "GetSubAccountDetail",
        "GetSignatureIdentificationList",
        "ListAllSmsProduct",
        "ListSignatureForAgent",
        "ListSmsTemplateForAgent",
        "ListSecondTemplate",
        "ListSmsSendLogForAgent",
        "ListTotalSendCountStatForAgent",
        "GetBatchTaskDetail",
        "GetBatchTaskList",
    }
)


@dataclass(frozen=True)
class ActionSpec:
    version: str
    method: str
    read_only: bool
    reconciliation_action: Optional[str]
    # None keeps the complete sanitized Result; a frozenset is an output allowlist.
    result_fields: Optional[frozenset]
    idempotency_field: Optional[str] = None
    required_result_fields: frozenset = frozenset()
    required_result_any: frozenset = frozenset()
    cli_supported: bool = True


COMMON_PAGE_FIELDS = {
    "List",
    "list",
    "Items",
    "items",
    "Total",
    "total",
    "Page",
    "page",
    "PageSize",
    "pageSize",
    "PageIndex",
    "pageIndex",
}
_MESSAGE_GROUP_FIELDS = {
    "SubAccount",
    "SubAccountName",
    "ChannelType",
    "ChannelTypes",
    "Status",
    "CreatedAt",
}
MESSAGE_GROUP_DETAIL_FIELDS = {
    "subAccountId",
    "subAccountName",
    "status",
    "channelTypeToIndustryConfig",
    "channelType",
    "channelTypeCn",
    "industry",
    "industryCn",
}
_QUALIFICATION_FIELDS = {
    "id",
    "purpose",
    "materialName",
    "businessCertificateName",
    "effectSignatures",
    "auditStatus",
    "auditOpinion",
    "auditedAt",
    "usable",
    "isOrder",
}
_QUALIFICATION_REQUIREMENT_FIELDS = {
    "isOnlyTwoElement",
    "isSkipOtherUse",
    "needOtherUseCheck",
    "operatorThreeElement",
    "needOperatorImage",
    "needOperatorMobile",
    "responsibleThreeElement",
    "needResponsibleImage",
    "needResponsibleMobile",
    "needBusinessCertificateImage",
}
_QUALIFICATION_OCR_FIELDS = {
    "businessCertificateType",
    "businessCertificateName",
    "unifiedSocialCreditIdentifier",
    "businessCertificateValidityPeriodStart",
    "businessCertificateValidityPeriodEnd",
    "legalPersonName",
    "personName",
    "personIDCard",
    "isIDCardValid",
}
_QUALIFICATION_CHECK_FIELDS = {"status", "ticket"}
_ACCOUNT_IDENTITY_FIELDS = {"businessName", "userType"}
_VERIFY_CODE_SEND_FIELDS = {"messageId"}
_VERIFY_CODE_CHECK_FIELDS = {"status", "sendType"}
_QUALIFICATION_UPLOAD_TOKEN_FIELDS = {
    "token",
    "accessKeyId",
    "secretAccessKey",
    "sessionToken",
    "expiredTime",
    "currentTime",
}
_SIGNATURE_FIELDS = {
    "Signature",
    "Description",
    "Source",
    "Domain",
    "Scene",
    "ProjectName",
    "AppIcp",
    "Trademark",
    "Status",
    "StatusDescription",
    "SubAccounts",
    "ChannelTypes",
    "ChannelType",
    "Purpose",
    "IdentificationId",
    "IdentificationID",
    "usable",
    "Usable",
    "CreatedAt",
    "UpdatedAt",
}
TEMPLATE_FIELDS = {
    "TemplateId",
    "templateId",
    "SecondTemplateId",
    "secondTemplateId",
    "TemplateName",
    "templateName",
    "Name",
    "name",
    "Content",
    "content",
    "TemplateParams",
    "templateParams",
    "ParamName",
    "ChannelType",
    "channelType",
    "Signature",
    "signature",
    "Signatures",
    "signatures",
    "SubAccounts",
    "subAccounts",
    "Status",
    "status",
    "StatusDescription",
    "statusDescription",
    "Description",
    "description",
    "Project",
    "project",
    "CreatedAt",
    "createdAt",
    "UpdatedAt",
    "updatedAt",
    "Area",
    "area",
    "ShortUrlConfig",
    "shortUrlConfig",
}
TEMPLATE_PARAM_FIELDS = {"name", "Name", "ParamName"}
TEMPLATE_SCALAR_LIST_FIELDS = {
    "Signatures",
    "signatures",
    "SubAccounts",
    "subAccounts",
}
_SHORT_URL_CONFIG_FIELDS = {
    "isEnabled",
    "belong",
    "isNeedClickDetails",
    "uaCheckStrategy",
}
_SIGNATURE_APPLICATION_FIELDS = {"applyId", "status", "reason"}
_TEMPLATE_APPLICATION_FIELDS = {
    "templateId",
    "status",
    "statusDescription",
    "auditOpinion",
}
_SEND_RESULT_FIELDS = {"MessageId", "MessageIds"}
_SEND_LOG_FIELDS = {
    "MessageId",
    "ErrorCode",
    "SendTime",
    "ReceiptTime",
    "TemplateId",
    "Signature",
    "SubAccount",
    "Count",
}
_STAT_FIELDS = {
    "TotalSendCount",
    "TotalAllSendCount",
    "TotalSendSuccessCount",
    "TotalReceiptSuccessCount",
    "TotalReceiptFailureCount",
}
_UPLOAD_FIELDS = {"file", "url"}
_TEMPLATE_DEMO_FIELDS = {"fileName", "value", "contentType", "size"}
TEMPLATE_DEMO_CSV_MEDIA_TYPES = frozenset(
    {
        "application/octet-stream",
        "application/csv",
        "application/vnd.ms-excel",
        "text/comma-separated-values",
        "text/csv",
    }
)
_BATCH_TASK_FIELDS = {
    "taskId",
    "subAccount",
    "taskName",
    "signature",
    "templateId",
    "templateName",
    "channelType",
    "scheduled",
    "sendTime",
    "fileUrl",
    "status",
    "totalCount",
}
_BATCH_CREATE_FIELDS = {"taskId", "dupCount", "totalCount"}
_PAGE_RESULT_FIELDS = frozenset({"List", "list", "Items", "items"})


def _fields(*groups: Iterable[str]) -> frozenset:
    result: Set[str] = set(COMMON_PAGE_FIELDS)
    for group in groups:
        result.update(group)
    return frozenset(result)


ACTION_REGISTRY: Dict[str, ActionSpec] = {
    "ListSubAccountForAgent": ActionSpec(
        SMS_API_VERSION,
        "POST",
        True,
        "ListSubAccountForAgent",
        _fields(_MESSAGE_GROUP_FIELDS),
        required_result_any=_PAGE_RESULT_FIELDS,
    ),
    "GetSubAccountDetail": ActionSpec(
        SMS_API_VERSION,
        "GET",
        True,
        "GetSubAccountDetail",
        frozenset(MESSAGE_GROUP_DETAIL_FIELDS),
        required_result_fields=frozenset({"subAccountId"}),
    ),
    "GetSignatureIdentificationList": ActionSpec(
        SMS_API_VERSION,
        "POST",
        True,
        "GetSignatureIdentificationList",
        _fields(_QUALIFICATION_FIELDS),
        required_result_any=_PAGE_RESULT_FIELDS,
    ),
    "GetAccountIdentRankForAgent": ActionSpec(
        SMS_API_VERSION,
        "GET",
        True,
        "GetAccountIdentRankForAgent",
        frozenset(_QUALIFICATION_REQUIREMENT_FIELDS),
        required_result_fields=frozenset(_QUALIFICATION_REQUIREMENT_FIELDS),
        cli_supported=False,
    ),
    "ListAllSmsProduct": ActionSpec(
        SMS_API_VERSION,
        "GET",
        True,
        "ListAllSmsProduct",
        frozenset(_ACCOUNT_IDENTITY_FIELDS),
        required_result_fields=frozenset(_ACCOUNT_IDENTITY_FIELDS),
        cli_supported=False,
    ),
    "GetMUploadParam": ActionSpec(
        SMS_API_VERSION,
        "GET",
        True,
        "GetMUploadParam",
        frozenset(_QUALIFICATION_UPLOAD_TOKEN_FIELDS),
        required_result_fields=frozenset({"token"}),
        cli_supported=False,
    ),
    "GetOCRLicenseForAgent": ActionSpec(
        SMS_API_VERSION,
        "POST",
        True,
        "GetOCRLicenseForAgent",
        frozenset(_QUALIFICATION_OCR_FIELDS),
        cli_supported=False,
    ),
    "ThreeElementEnterpriseCheckForAgent": ActionSpec(
        SMS_API_VERSION,
        "POST",
        True,
        "ThreeElementEnterpriseCheckForAgent",
        frozenset(_QUALIFICATION_CHECK_FIELDS),
        required_result_fields=frozenset({"status"}),
        cli_supported=False,
    ),
    "ThreeElementPersonCheckForAgent": ActionSpec(
        SMS_API_VERSION,
        "POST",
        True,
        "ThreeElementPersonCheckForAgent",
        frozenset(_QUALIFICATION_CHECK_FIELDS),
        required_result_fields=frozenset({"status"}),
        cli_supported=False,
    ),
    "ApplySignatureIdentificationForAgent": ActionSpec(
        SMS_API_VERSION,
        "POST",
        False,
        "GetSignatureIdentificationList",
        frozenset(),
        cli_supported=False,
    ),
    "SendSmsVerifyCodeByMobile": ActionSpec(
        SMS_API_VERSION,
        "POST",
        False,
        None,
        frozenset(_VERIFY_CODE_SEND_FIELDS),
        required_result_fields=frozenset({"messageId"}),
        cli_supported=False,
    ),
    "CheckSmsVerifyCodeByMobile": ActionSpec(
        SMS_API_VERSION,
        "POST",
        False,
        None,
        frozenset(_VERIFY_CODE_CHECK_FIELDS),
        required_result_fields=frozenset({"status"}),
        cli_supported=False,
    ),
    "ListSignatureForAgent": ActionSpec(
        SMS_API_VERSION,
        "POST",
        True,
        "ListSignatureForAgent",
        _fields(_SIGNATURE_FIELDS),
        required_result_any=_PAGE_RESULT_FIELDS,
    ),
    "ListSmsTemplateForAgent": ActionSpec(
        SMS_API_VERSION,
        "POST",
        True,
        "ListSmsTemplateForAgent",
        _fields(TEMPLATE_FIELDS),
        required_result_any=_PAGE_RESULT_FIELDS,
    ),
    "ListSecondTemplate": ActionSpec(
        SMS_API_VERSION,
        "GET",
        True,
        "ListSecondTemplate",
        _fields(TEMPLATE_FIELDS),
        required_result_any=_PAGE_RESULT_FIELDS,
    ),
    "ApplySmsSignatureV2": ActionSpec(
        SMS_API_VERSION,
        "POST",
        False,
        "ListSignatureForAgent",
        frozenset(_SIGNATURE_APPLICATION_FIELDS),
        required_result_any=frozenset({"applyId", "status"}),
    ),
    "ApplySmsTemplateV2": ActionSpec(
        SMS_API_VERSION,
        "POST",
        False,
        "ListSmsTemplateForAgent",
        frozenset(_TEMPLATE_APPLICATION_FIELDS),
        required_result_any=frozenset({"templateId", "status"}),
    ),
    "SendSmsForAgent": ActionSpec(
        SMS_API_VERSION,
        "POST",
        False,
        "ListSmsSendLogForAgent",
        frozenset(_SEND_RESULT_FIELDS),
        required_result_any=frozenset({"MessageId", "MessageIds"}),
    ),
    "ListSmsSendLogForAgent": ActionSpec(
        SMS_API_VERSION,
        "POST",
        True,
        "ListSmsSendLogForAgent",
        _fields(_SEND_LOG_FIELDS),
        required_result_any=_PAGE_RESULT_FIELDS,
    ),
    "ListTotalSendCountStatForAgent": ActionSpec(
        SMS_API_VERSION,
        "POST",
        True,
        "ListTotalSendCountStatForAgent",
        _fields(_STAT_FIELDS),
        required_result_any=frozenset(_STAT_FIELDS),
    ),
    "GetUploadTosURL": ActionSpec(
        SMS_API_VERSION,
        "GET",
        False,
        None,
        frozenset(_UPLOAD_FIELDS),
        required_result_fields=frozenset(_UPLOAD_FIELDS),
    ),
    "TemplateUploadDemo": ActionSpec(
        SMS_API_VERSION,
        "POST",
        True,
        "TemplateUploadDemo",
        frozenset(_TEMPLATE_DEMO_FIELDS),
    ),
    "SetBatchTask": ActionSpec(
        SMS_API_VERSION,
        "POST",
        False,
        "GetBatchTaskDetail",
        frozenset(_BATCH_CREATE_FIELDS),
        required_result_fields=frozenset({"taskId"}),
    ),
    "GetBatchTaskDetail": ActionSpec(
        SMS_API_VERSION,
        "GET",
        True,
        "GetBatchTaskDetail",
        frozenset(_BATCH_TASK_FIELDS),
        required_result_fields=frozenset({"taskId"}),
    ),
    "GetBatchTaskList": ActionSpec(
        SMS_API_VERSION,
        "GET",
        True,
        "GetBatchTaskList",
        _fields(_BATCH_TASK_FIELDS),
        required_result_any=_PAGE_RESULT_FIELDS,
    ),
    "ConsentBatchTask": ActionSpec(
        SMS_API_VERSION,
        "POST",
        False,
        "GetBatchTaskDetail",
        frozenset(),
    ),
    "DeleteBatchTask": ActionSpec(
        SMS_API_VERSION,
        "POST",
        False,
        "GetBatchTaskDetail",
        frozenset(),
    ),
}
