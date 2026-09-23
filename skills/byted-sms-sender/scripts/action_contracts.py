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
        "GetSubAccountListForAgent",
        "GetSubAccountDetail",
        "GetSignatureIdentificationList",
        "ListAllSmsProduct",
        "ListSignatureForAgent",
        "ListSignaturesForAgent",
        "ListSmsTemplateForAgent",
        "ListBatchTemplatesForAgent",
        "ListSecondTemplate",
        "ListSmsSendLogForAgent",
        "GetTotalSendCountStatV4ForAgent",
        "GetBatchTaskDetail",
        "GetBatchTaskList",
    }
)


# Public account queries only; private qualification/OCR/upload Actions stay in forms.
PUBLIC_QUERY_ACTIONS = LIVE_VALIDATION_ACTIONS | {
    "ValidateBatchTaskContentForAgent", "TemplateUploadDemoForAgent",
}


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
    request_timeout: Optional[float] = None
    private_result_fields: frozenset = frozenset()
    # Material APIs retain code-only diagnostics; public resource APIs can expose the message.
    public_error_message: bool = False


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
    "ScannedTotal",
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
_SIGNATURE_APPLICATION_FIELDS = {"applyId", "status", "reason"}
_TEMPLATE_APPLICATION_FIELDS = {
    "templateId",
    "status",
    "statusDescription",
    "auditOpinion",
}
_SEND_RESULT_FIELDS = {"MessageId", "MessageIds"}
_STAT_FIELDS = {
    "TotalSendCount",
    "TotalAllSendCount",
    "TotalSendSuccessCount",
    "TotalReceiptSuccessCount",
    "TotalReceiptFailureCount",
    "TotalNoReceipt72HourCount",
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
    "status",
    "totalCount",
    "dupCount",
    "sendContent",
}
_BATCH_CREATE_FIELDS = {
    "taskId",
    "totalCount",
    "dupCount",
}
_PAGE_RESULT_FIELDS = frozenset({"List", "list", "Items", "items"})


def _fields(*groups: Iterable[str]) -> frozenset:
    result: Set[str] = set(COMMON_PAGE_FIELDS)
    for group in groups:
        result.update(group)
    return frozenset(result)


_RESOURCE_PRIVATE_FIELDS = frozenset({
    "operatorperson", "responsiblepersoninfo", "legalperson", "powerofattorney",
    "othermaterials", "businesscertificate", "legalpersonname", "authfilelist",
    "appicpfilelist", "trademarkfilelist", "fileurl", "filecontent",
})

ACTION_REGISTRY: Dict[str, ActionSpec] = {
    "ListSubAccountForAgent": ActionSpec(
        SMS_API_VERSION,
        "POST",
        True,
        "ListSubAccountForAgent",
        None,
        required_result_any=_PAGE_RESULT_FIELDS,
        private_result_fields=_RESOURCE_PRIVATE_FIELDS,
        cli_supported=False,
    ),
    "GetSubAccountListForAgent": ActionSpec(
        SMS_API_VERSION,
        "POST",
        True,
        "GetSubAccountListForAgent",
        None,
        required_result_any=_PAGE_RESULT_FIELDS,
        private_result_fields=_RESOURCE_PRIVATE_FIELDS,
        cli_supported=False,
    ),
    "GetSubAccountDetail": ActionSpec(
        SMS_API_VERSION,
        "GET",
        True,
        "GetSubAccountDetail",
        None,
        required_result_fields=frozenset({"subAccountId"}),
        private_result_fields=_RESOURCE_PRIVATE_FIELDS,
    ),
    "GetSignatureIdentificationList": ActionSpec(
        SMS_API_VERSION,
        "POST",
        True,
        "GetSignatureIdentificationList",
        None,
        required_result_any=_PAGE_RESULT_FIELDS,
        private_result_fields=_RESOURCE_PRIVATE_FIELDS,
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
    "ValidateBatchTaskContentForAgent": ActionSpec(
        SMS_API_VERSION,
        "POST",
        True,
        "ValidateBatchTaskContentForAgent",
        frozenset({"Approved", "Reason"}),
        required_result_fields=frozenset({"Approved"}),
        cli_supported=False,
        public_error_message=True,
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
        public_error_message=True,
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
        None,
        required_result_any=_PAGE_RESULT_FIELDS,
        private_result_fields=_RESOURCE_PRIVATE_FIELDS,
    ),
    "ListSignaturesForAgent": ActionSpec(
        SMS_API_VERSION,
        "POST",
        True,
        "ListSignaturesForAgent",
        None,
        required_result_any=_PAGE_RESULT_FIELDS,
        cli_supported=False,
        private_result_fields=_RESOURCE_PRIVATE_FIELDS,
    ),
    "ListSmsTemplateForAgent": ActionSpec(
        SMS_API_VERSION,
        "POST",
        True,
        "ListSmsTemplateForAgent",
        None,
        required_result_any=_PAGE_RESULT_FIELDS,
        private_result_fields=_RESOURCE_PRIVATE_FIELDS,
        cli_supported=False,
    ),
    "ListBatchTemplatesForAgent": ActionSpec(
        SMS_API_VERSION,
        "POST",
        True,
        "ListBatchTemplatesForAgent",
        None,
        required_result_any=_PAGE_RESULT_FIELDS,
        cli_supported=False,
        private_result_fields=_RESOURCE_PRIVATE_FIELDS,
    ),
    "ListSecondTemplate": ActionSpec(
        SMS_API_VERSION,
        "GET",
        True,
        "ListSecondTemplate",
        None,
        required_result_any=_PAGE_RESULT_FIELDS,
        private_result_fields=_RESOURCE_PRIVATE_FIELDS,
    ),
    "ApplySmsSignatureV2": ActionSpec(
        SMS_API_VERSION,
        "POST",
        False,
        "ListSignatureForAgent",
        frozenset(_SIGNATURE_APPLICATION_FIELDS),
        required_result_any=frozenset({"applyId", "status"}),
        public_error_message=True,
    ),
    "ApplySmsTemplateV2": ActionSpec(
        SMS_API_VERSION,
        "POST",
        False,
        "ListSmsTemplateForAgent",
        frozenset(_TEMPLATE_APPLICATION_FIELDS),
        required_result_any=frozenset({"templateId", "status"}),
        public_error_message=True,
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
        None,
        required_result_any=_PAGE_RESULT_FIELDS,
        private_result_fields=frozenset({"mobile", "content"}),
    ),
    "GetTotalSendCountStatV4ForAgent": ActionSpec(
        SMS_API_VERSION,
        "POST",
        True,
        "GetTotalSendCountStatV4ForAgent",
        None,
        required_result_any=frozenset(_STAT_FIELDS),
        cli_supported=False,
    ),
    "GetUploadTosURL": ActionSpec(
        SMS_API_VERSION,
        "GET",
        False,
        None,
        frozenset(_UPLOAD_FIELDS),
        required_result_fields=frozenset(_UPLOAD_FIELDS),
    ),
    "TemplateUploadDemoForAgent": ActionSpec(
        SMS_API_VERSION,
        "POST",
        True,
        "TemplateUploadDemoForAgent",
        frozenset(_TEMPLATE_DEMO_FIELDS),
        cli_supported=False,
    ),
    "SetBatchTaskForAgent": ActionSpec(
        SMS_API_VERSION,
        "POST",
        False,
        "GetBatchTaskDetail",
        frozenset(_BATCH_CREATE_FIELDS),
        idempotency_field="idempotencyKey",
        required_result_fields=frozenset(_BATCH_CREATE_FIELDS),
        cli_supported=False,
        request_timeout=60.0,
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
