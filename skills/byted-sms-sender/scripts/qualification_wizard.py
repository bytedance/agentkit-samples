# Copyright (c) 2026 Beijing Volcano Engine Technology Co., Ltd. and/or its affiliates.
#
# Licensed under the Apache License, Version 2.0 (the "License");
"""Loopback-only qualification draft, review, replacement, and submission UI."""

from __future__ import annotations

import datetime
import hmac
import json
import mimetypes
import re
import secrets
import sys
import threading
import time
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any, Callable, Dict, Mapping, MutableMapping, Optional
from urllib import parse

from api_client import SmsApiClient
from qualification_display import (
    QualificationDisplayAdapter,
    browser_display_adapter,
)
from qualification_upload import (
    BUSINESS_CHECK_SKIP_TICKET,
    MAX_IMAGE_BYTES,
    QualificationUploadError,
    check_mobile_verification_code,
    check_signature_qualification_information,
    create_signature_qualification,
    get_account_identity,
    get_account_ident_rank,
    normalize_check_status,
    ocr_identity_document_images,
    send_mobile_verification_code,
    upload_and_ocr_business_certificate_bytes,
    upload_and_ocr_identity_document_bytes,
    upload_qualification_file_bytes,
)


MAX_JSON_BYTES = 64 * 1024
QUALIFICATION_DISCONNECT_TIMEOUT_SECONDS = 5 * 60
QUALIFICATION_DETACH_GRACE_SECONDS = 60
QUALIFICATION_IDLE_TIMEOUT_SECONDS = 30 * 60
QUALIFICATION_CONTEXT_HEADER = "X-Qualification-Context"
PERSON_FILE_TYPES = {
    "operator": (8, 9),
    "responsible": (10, 11),
    "legal": (18, 19),
}
LEGAL_CERTIFICATE_TYPES = frozenset({0, 1, 2, 3, 4, 9})
LEGAL_DOCUMENT_FILE_TYPES = {
    1: 12,
    2: 13,
    3: 14,
    4: 15,
    9: 6,
}
PERSON_LABELS = {
    "operator": "经办人",
    "responsible": "责任人",
    "legal": "法人",
}


def _text(value: Any, *, maximum: int = 256) -> str:
    if not isinstance(value, str):
        raise ValueError
    value = value.strip()
    if not value or len(value) > maximum:
        raise ValueError
    return value


def _optional_text(value: Any, *, maximum: int = 256) -> str:
    if value is None:
        return ""
    if not isinstance(value, str):
        raise ValueError
    value = value.strip()
    if len(value) > maximum:
        raise ValueError
    return value


def _date(value: Any) -> str:
    value = _text(value, maximum=10)
    parsed = datetime.date.fromisoformat(value)
    if parsed.isoformat() != value:
        raise ValueError
    return value


def _id_card(value: Any, *, required: bool = True) -> str:
    if value is None:
        value = ""
    if not isinstance(value, str):
        raise ValueError
    value = value.strip().upper()
    if not value and not required:
        return ""
    if not re.fullmatch(r"[0-9]{17}[0-9X]", value):
        raise ValueError
    return value


def _mobile(value: Any, *, required: bool) -> str:
    if value is None:
        value = ""
    if not isinstance(value, str):
        raise ValueError
    value = value.strip()
    if value and not re.fullmatch(r"1[3-9][0-9]{9}", value):
        raise ValueError
    if required and not value:
        raise ValueError
    return value


def _person_requirement(rank: Mapping[str, Any], role: str, kind: str) -> bool:
    """Return the deterministic fields required before a role can be saved."""
    if kind not in ("image", "mobile"):
        raise ValueError
    if role == "legal":
        return False
    if role not in ("operator", "responsible"):
        raise ValueError
    prefix = "Operator" if role == "operator" else "Responsible"
    if kind == "image":
        return bool(rank.get("need" + prefix + "Image"))
    return bool(
        rank.get(role + "ThreeElement") or rank.get("need" + prefix + "Mobile")
    )


def _legal_person_name(business: Any, submitted: Any) -> str:
    """Keep the business certificate as the sole source of the legal name."""
    if not isinstance(business, Mapping):
        raise QualificationUploadError(
            "business_info_required", "请先保存营业证件信息。"
        )
    expected = _text(business.get("legalPersonName"))
    try:
        actual = _text(submitted)
    except ValueError as error:
        raise QualificationUploadError(
            "legal_name_mismatch", "法人姓名必须与营业证件一致。"
        ) from error
    if actual != expected:
        raise QualificationUploadError(
            "legal_name_mismatch", "法人姓名必须与营业证件一致。"
        )
    return expected


def _public_check(state: Mapping[str, Any], target: str) -> Dict[str, Any]:
    check = state.get("checks", {}).get(target)
    if not isinstance(check, Mapping):
        return {"attempted": False, "matched": False, "canContinue": False}
    return {
        "attempted": True,
        "matched": bool(check.get("matched")),
        "canContinue": bool(check.get("canContinue")),
        "status": normalize_check_status(check.get("status")),
        "forceSkip": check.get("ticket") == BUSINESS_CHECK_SKIP_TICKET,
    }


def _verification_params(state: Mapping[str, Any], target: str) -> Dict[str, Any]:
    sections = state["sections"]
    if target == "business":
        business = sections.get("business")
        if not isinstance(business, Mapping):
            raise QualificationUploadError(
                "qualification_check_required", "请先保存营业证件信息。"
            )
        return {
            "businessCertificateName": business["businessCertificateName"],
            "unifiedSocialCreditIdentifier": business[
                "unifiedSocialCreditIdentifier"
            ],
            "legalPersonName": business["legalPersonName"],
        }
    if target not in ("legal", "operator", "responsible"):
        raise QualificationUploadError(
            "qualification_check_invalid", "不支持当前信息校验。"
        )
    if target == "responsible" and state.get("sameOperator") is True:
        raise QualificationUploadError(
            "qualification_check_not_needed", "责任人与经办人相同，无需重复校验。"
        )
    person = sections.get(target)
    if not isinstance(person, Mapping):
        raise QualificationUploadError(
            "qualification_check_required", "请先保存{}信息。".format(PERSON_LABELS[target])
        )
    mobile_required = target != "legal" and bool(
        state["rank"].get(target + "ThreeElement")
    )
    return {
        "personName": person["personName"],
        "personIDCard": person["personIDCard"],
        "personMobile": person["personMobile"] if mobile_required else "",
    }


def _has_identity_image_pair(section: Any) -> bool:
    if not isinstance(section, Mapping):
        return False
    image_uris = section.get("imageUris")
    return isinstance(image_uris, Mapping) and bool(
        image_uris.get("front") and image_uris.get("back")
    )


def _mobile_verification_needed(state: Mapping[str, Any], role: str) -> bool:
    if not state.get("mobileVerificationRequired"):
        return False
    person = state.get("sections", {}).get(role)
    return isinstance(person, Mapping) and bool(person.get("personMobile"))


def _mobile_verified(state: Mapping[str, Any], role: str) -> bool:
    if role == "responsible" and state.get("sameOperator") is True:
        role = "operator"
    if not _mobile_verification_needed(state, role):
        return True
    person = state.get("sections", {}).get(role)
    verification = state.get("mobileVerifications", {}).get(role)
    return bool(
        isinstance(person, Mapping)
        and isinstance(verification, Mapping)
        and verification.get("verified") is True
        and verification.get("mobile") == person.get("personMobile")
    )


def _public_state(state: Mapping[str, Any]) -> Dict[str, Any]:
    sections = state["sections"]
    same_operator = state.get("sameOperator") is True
    power_required = bool(
        state.get("purpose") == 2 and state["rank"].get("needOtherUseCheck")
    )
    public_sections = {name: name in sections for name in PERSON_FILE_TYPES}
    public_sections["responsible"] = bool(
        public_sections["responsible"]
        or (same_operator and public_sections["operator"])
    )
    public_checks = {
        target: _public_check(state, target)
        for target in ("business", "legal", "operator", "responsible")
    }
    if same_operator:
        public_checks["responsible"] = dict(public_checks["operator"])
    mobile_verifications = {
        role: _mobile_verified(state, role)
        for role in ("operator", "responsible")
    }
    legal = sections.get("legal")
    legal_check_required = bool(
        isinstance(legal, Mapping)
        and int(legal.get("certificateType") or 0) == 0
        and legal.get("personIDCard")
    )
    saved_data: Dict[str, Any] = {
        "business": {},
        "people": {},
    }
    business = sections.get("business")
    if isinstance(business, Mapping):
        saved_data["business"] = {
            key: business.get(key)
            for key in (
                "businessCertificateType",
                "businessCertificateName",
                "unifiedSocialCreditIdentifier",
                "legalPersonName",
                "businessCertificateValidityPeriodStart",
                "businessCertificateValidityPeriodEnd",
            )
        }
        saved_data["business"]["hasImage"] = bool(business.get("imageUri"))
    for role in PERSON_FILE_TYPES:
        person = sections.get(role)
        if isinstance(person, Mapping):
            saved_data["people"][role] = {
                key: person.get(key)
                for key in (
                    "certificateType",
                    "personName",
                    "personIDCard",
                    "personMobile",
                )
            }
            saved_data["people"][role]["hasImages"] = _has_identity_image_pair(person)
            saved_data["people"][role]["hasIdentityImages"] = _has_identity_image_pair(
                person
            )
            saved_data["people"][role]["hasDocuments"] = bool(
                person.get("documents")
            )
    return {
        "revision": state["revision"],
        "materialSaved": bool(state.get("materialName")),
        "baseSaved": bool(state.get("baseSaved")),
        "materialName": state.get("materialName") or "",
        "materialNameSource": state.get("materialNameSource") or "auto",
        "purpose": state.get("purpose"),
        "sameOperator": state.get("sameOperator"),
        "legalAcknowledged": bool(state.get("legalAcknowledged")),
        "authorizationAcknowledged": bool(state.get("authorizationAcknowledged")),
        "sections": public_sections,
        "businessSaved": "business" in sections,
        "powerOfAttorneyRequired": power_required,
        "powerOfAttorneySaved": "powerOfAttorney" in sections,
        "otherMaterialCount": len(sections.get("otherMaterials") or []),
        "authorizee": state.get("authorizee") or "",
        "authorizer": (
            business.get("businessCertificateName")
            if isinstance(business, Mapping)
            else ""
        ),
        "legalCheckRequired": legal_check_required,
        "readyForPreview": all(key in sections for key in ("business", "operator"))
        and public_sections["responsible"]
        and public_checks["business"]["canContinue"]
        and (not legal_check_required or public_checks["legal"]["matched"])
        and public_checks["operator"]["matched"]
        and public_checks["responsible"]["matched"]
        and mobile_verifications["operator"]
        and mobile_verifications["responsible"]
        and bool(state.get("materialName"))
        and bool(state.get("legalAcknowledged"))
        and (not power_required or "powerOfAttorney" in sections)
        and (
            state.get("purpose") != 2
            or (
                bool(state.get("authorizationAcknowledged"))
                and bool(state.get("authorizee"))
            )
        ),
        "rank": dict(state["rank"]),
        "mobileVerificationRequired": bool(
            state.get("mobileVerificationRequired")
        ),
        "mobileVerifications": mobile_verifications,
        "savedData": saved_data,
        "checks": public_checks,
    }


def _person_payload(section: Mapping[str, Any], role: str) -> Dict[str, Any]:
    front_type, back_type = PERSON_FILE_TYPES[role]
    certificate_type = int(section.get("certificateType") or 0)
    payload = {
        "certificateType": certificate_type,
        "personCertificate": [],
        "personName": section["personName"],
        "personIDCard": section["personIDCard"],
        "personMobile": section["personMobile"],
    }
    uris = section.get("imageUris")
    suffixes = section.get("imageSuffixes")
    if isinstance(uris, Mapping) and isinstance(suffixes, Mapping):
        payload["personCertificate"] = [
            {
                "fileType": front_type,
                "fileContent": uris["front"],
                "fileSuffix": suffixes["front"],
            },
            {
                "fileType": back_type,
                "fileContent": uris["back"],
                "fileSuffix": suffixes["back"],
            },
        ]
    documents = section.get("documents")
    if role == "legal" and certificate_type in LEGAL_DOCUMENT_FILE_TYPES and isinstance(
        documents, list
    ):
        payload["personCertificate"] = [
            {
                "fileType": LEGAL_DOCUMENT_FILE_TYPES[certificate_type],
                "fileContent": item["imageUri"],
                "fileSuffix": item["imageSuffix"],
            }
            for item in documents
            if isinstance(item, Mapping)
            and item.get("imageUri")
            and item.get("imageSuffix")
        ]
    return payload


def _submission_payload(state: Mapping[str, Any]) -> Dict[str, Any]:
    sections = state["sections"]
    business = sections["business"]
    checks = state["checks"]
    operator_ticket = checks["operator"]["ticket"]
    responsible_ticket = (
        operator_ticket
        if state.get("sameOperator") is True
        else checks["responsible"]["ticket"]
    )
    payload: Dict[str, Any] = {
        "id": 0,
        "purpose": state["purpose"],
        "materialName": state["materialName"],
        "businessInfo": {
            "businessCertificateType": business["businessCertificateType"],
            "businessCertificate": {},
            "businessCertificateName": business["businessCertificateName"],
            "unifiedSocialCreditIdentifier": business[
                "unifiedSocialCreditIdentifier"
            ],
            "businessCertificateValidityPeriodStart": business[
                "businessCertificateValidityPeriodStart"
            ],
            "businessCertificateValidityPeriodEnd": business[
                "businessCertificateValidityPeriodEnd"
            ],
            "legalPersonName": business["legalPersonName"],
        },
        "operatorPerson": _person_payload(sections["operator"], "operator"),
        "responsiblePersonInfo": _person_payload(
            sections["operator"]
            if state.get("sameOperator") is True
            else sections["responsible"],
            "responsible",
        ),
        "powerOfAttorney": [],
        "otherMaterials": [],
        "effectSignatures": [],
        "from": "vconsole",
        "sameOperator": state.get("sameOperator") is True,
        "businessCheckTicket": checks["business"]["ticket"],
        "operatorCheckTicket": operator_ticket,
        "responsibleCheckTicket": responsible_ticket,
    }
    legal = sections.get("legal")
    if isinstance(legal, Mapping):
        payload["legalPerson"] = _person_payload(legal, "legal")
        legal_check = checks.get("legal")
        if isinstance(legal_check, Mapping) and legal_check.get("ticket"):
            payload["legalCheckTicket"] = legal_check["ticket"]
    if business.get("imageUri"):
        payload["businessInfo"]["businessCertificate"] = {
            "fileType": business["businessCertificateType"],
            "fileContent": business["imageUri"],
            "fileSuffix": business["imageSuffix"],
        }
    other_materials = sections.get("otherMaterials")
    if isinstance(other_materials, list):
        payload["otherMaterials"] = [
            {
                "fileType": 6,
                "fileContent": item["imageUri"],
                "fileSuffix": item["imageSuffix"],
            }
            for item in other_materials
            if isinstance(item, Mapping)
            and item.get("imageUri")
            and item.get("imageSuffix")
        ]
    rank = state["rank"]
    if state["purpose"] == 2:
        payload["authorizer"] = business["businessCertificateName"]
        payload["authorizee"] = state["authorizee"]
    if state["purpose"] == 2 and rank.get("needOtherUseCheck"):
        power = sections["powerOfAttorney"]
        payload["powerOfAttorney"] = [
            {
                "fileType": 5,
                "fileContent": power["imageUri"],
                "fileSuffix": power["imageSuffix"],
            }
        ]
    return payload


def _preview(state: Mapping[str, Any]) -> Dict[str, Any]:
    sections = state["sections"]
    business = sections["business"]
    people = {}
    for role in PERSON_FILE_TYPES:
        if role == "responsible" and state.get("sameOperator") is True:
            person = sections.get("operator")
        else:
            person = sections.get(role)
        if isinstance(person, Mapping):
            people[role] = {
                "label": PERSON_LABELS[role],
                "personName": person["personName"],
                "personIDCard": person["personIDCard"],
                "personMobile": person["personMobile"],
                "reusedFromOperator": bool(
                    role == "responsible" and state.get("sameOperator") is True
                ),
            }
    return {
        "revision": state["revision"],
        "materialName": state["materialName"],
        "purpose": "他用" if state["purpose"] == 2 else "自用",
        "powerOfAttorney": "已提供"
        if "powerOfAttorney" in sections
        else "无需提供",
        "authorization": (
            {
                "authorizer": business["businessCertificateName"],
                "authorizee": state["authorizee"],
                "otherMaterialCount": len(sections.get("otherMaterials") or []),
            }
            if state["purpose"] == 2
            else None
        ),
        "business": {
            key: business[key]
            for key in (
                "businessCertificateName",
                "unifiedSocialCreditIdentifier",
                "legalPersonName",
                "businessCertificateValidityPeriodStart",
                "businessCertificateValidityPeriodEnd",
            )
        },
        "people": people,
        "checks": {
            "business": "通过"
            if state["checks"]["business"]["matched"]
            else "未通过自动校验，将转人工审核",
            "legal": (
                "通过"
                if state.get("checks", {}).get("legal", {}).get("matched")
                else "无需校验"
            ),
            "operator": "通过",
            "responsible": "同经办人，复用经办人校验"
            if state.get("sameOperator") is True
            else "通过",
        },
    }


_ASSET_DIRECTORY = Path(__file__).resolve().parents[1] / "assets"
_HTML = (_ASSET_DIRECTORY / "qualification_wizard.html").read_text(encoding="utf-8")
_STATIC_ASSETS = {
    "/qualification-static/react.production.min.js": (
        _ASSET_DIRECTORY / "qualification_wizard_vendor" / "react.production.min.js"
    ),
    "/qualification-static/react-dom.production.min.js": (
        _ASSET_DIRECTORY
        / "qualification_wizard_vendor"
        / "react-dom.production.min.js"
    ),
    "/qualification-static/arco.min.js": (
        _ASSET_DIRECTORY / "qualification_wizard_vendor" / "arco.min.js.br"
    ),
    "/qualification-static/arco-icon.min.js": (
        _ASSET_DIRECTORY / "qualification_wizard_vendor" / "arco-icon.min.js.br"
    ),
    "/qualification-static/arco.min.css": (
        _ASSET_DIRECTORY / "qualification_wizard_vendor" / "arco.min.css.br"
    ),
    "/qualification-static/qualification_wizard.css": (
        _ASSET_DIRECTORY / "qualification_wizard.css"
    ),
    "/qualification-static/qualification_wizard.js": (
        _ASSET_DIRECTORY / "qualification_wizard.js"
    ),
}


def run_qualification_wizard(
    client: SmsApiClient,
    *,
    display: Optional[QualificationDisplayAdapter] = None,
    cancel_event: Optional[threading.Event] = None,
    on_display_ready: Optional[Callable[[], None]] = None,
    disconnect_timeout_seconds: float = QUALIFICATION_DISCONNECT_TIMEOUT_SECONDS,
    detach_grace_seconds: float = QUALIFICATION_DETACH_GRACE_SECONDS,
    idle_timeout_seconds: float = QUALIFICATION_IDLE_TIMEOUT_SECONDS,
) -> Dict[str, Any]:
    """Run one local draft wizard through the selected presentation adapter."""
    if min(
        disconnect_timeout_seconds,
        detach_grace_seconds,
        idle_timeout_seconds,
    ) <= 0:
        raise ValueError("Qualification lifecycle timeouts must be positive.")
    display = display or browser_display_adapter()
    cancel_event = cancel_event or threading.Event()
    rank = get_account_ident_rank(client)
    account_identity = get_account_identity(client)
    token = secrets.token_urlsafe(24)
    lock = threading.Lock()
    started_at = time.monotonic()
    state: Dict[str, Any] = {
        "rank": rank,
        "revision": 0,
        "materialName": "",
        "materialNameSource": "auto",
        "baseSaved": False,
        "purpose": 1,
        "sameOperator": None,
        "accountBusinessName": account_identity["businessName"],
        "userType": account_identity["userType"],
        "mobileVerificationRequired": account_identity["userType"] == "smb",
        "mobileVerifications": {},
        "authorizee": "",
        "legalAcknowledged": False,
        "authorizationAcknowledged": False,
        "sections": {},
        "checks": {},
        "pending": {},
        "done": False,
        "abandoned": False,
        "terminationReason": "",
        "result": None,
        "lastActivity": started_at,
        "lastHeartbeat": started_at,
        "detachedAt": None,
    }

    def touch(*, active: bool) -> None:
        now = time.monotonic()
        with lock:
            state["lastHeartbeat"] = now
            state["detachedAt"] = None
            if active:
                state["lastActivity"] = now

    def stop(reason: str) -> None:
        with lock:
            if state["done"]:
                return
            state["terminationReason"] = reason
            state["abandoned"] = True
            state["done"] = True

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: Any) -> None:
            return

        def _json(self, status_code: int, payload: Mapping[str, Any]) -> None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status_code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _asset(self, path: str) -> bool:
            asset_path = _STATIC_ASSETS.get(path)
            if asset_path is None:
                return False
            try:
                body = asset_path.read_bytes()
            except OSError:
                self.send_error(HTTPStatus.NOT_FOUND)
                return True
            content_type, content_encoding = mimetypes.guess_type(asset_path.name)
            self.send_response(HTTPStatus.OK)
            self.send_header(
                "Content-Type",
                "{}; charset=utf-8".format(content_type or "application/octet-stream"),
            )
            if content_encoding:
                self.send_header("Content-Encoding", content_encoding)
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return True

        def _authorized(self) -> bool:
            supplied = self.headers.get(QUALIFICATION_CONTEXT_HEADER, "")
            return hmac.compare_digest(supplied, token)

        def _body(self, maximum: int = MAX_JSON_BYTES) -> bytes:
            try:
                length = int(self.headers.get("Content-Length") or "0")
            except ValueError as exc:
                raise ValueError from exc
            if length <= 0 or length > maximum:
                raise ValueError
            return self.rfile.read(length)

        def _document(self) -> MutableMapping[str, Any]:
            value = json.loads(self._body().decode("utf-8"))
            if not isinstance(value, MutableMapping):
                raise ValueError
            return value

        def do_GET(self) -> None:
            request_path = parse.urlsplit(self.path).path
            if request_path.startswith("/qualification-static/"):
                if not self._asset(request_path):
                    self.send_error(HTTPStatus.NOT_FOUND)
                return
            if request_path == "/":
                touch(active=True)
                sys.stderr.write(
                    "QUALIFICATION_DISPLAY_EVENT "
                    + json.dumps(
                        {
                            "event": "wizard_document_requested",
                            "display": display.name,
                        },
                        ensure_ascii=False,
                        separators=(",", ":"),
                    )
                    + "\n"
                )
                sys.stderr.flush()
                body = _HTML.replace(
                    "__MAX_IMAGE_BYTES__", str(MAX_IMAGE_BYTES)
                ).encode("utf-8")
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Cache-Control", "no-store")
                self.send_header(
                    "Content-Security-Policy",
                    "default-src 'none'; script-src 'self'; style-src 'self' 'unsafe-inline'; connect-src 'self'; img-src 'self' blob: data:; font-src 'self'; form-action 'none'; base-uri 'none'; object-src 'none'",
                )
                if not display.allows_embedding:
                    self.send_header("X-Frame-Options", "DENY")
                self.send_header("Referrer-Policy", "no-referrer")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            if not self._authorized():
                self.send_error(HTTPStatus.NOT_FOUND)
                return
            touch(active=True)
            if request_path == "/api/state":
                with lock:
                    public = _public_state(state)
                self._json(HTTPStatus.OK, {"success": True, "state": public})
                return
            self.send_error(HTTPStatus.NOT_FOUND)

        def do_POST(self) -> None:
            if not self._authorized():
                self.send_error(HTTPStatus.NOT_FOUND)
                return
            path = parse.urlsplit(self.path).path
            query = parse.parse_qs(parse.urlsplit(self.path).query)
            try:
                if path == "/api/heartbeat":
                    document = self._document()
                    if on_display_ready is not None:
                        on_display_ready()
                    touch(active=document.get("active") is True)
                    self._json(HTTPStatus.OK, {"success": True})
                    return
                if path == "/api/detach":
                    with lock:
                        state["detachedAt"] = time.monotonic()
                    self._json(HTTPStatus.OK, {"success": True})
                    return
                touch(active=True)
                if path == "/api/base":
                    document = self._document()
                    purpose = int(document.get("purpose") or 0)
                    if purpose not in (1, 2):
                        raise ValueError
                    material_name = str(document.get("materialName") or "").strip()
                    if not material_name or len(material_name) > 20:
                        raise ValueError
                    account_business_name = (
                        state["accountBusinessName"] if purpose == 2 else ""
                    )
                    with lock:
                        old_purpose = state.get("purpose")
                        old_authorizee = state.get("authorizee")
                        state["purpose"] = purpose
                        state["materialName"] = material_name
                        state["materialNameSource"] = "manual" if material_name else "auto"
                        state["baseSaved"] = True
                        state["authorizee"] = account_business_name
                        if (
                            old_purpose != purpose
                            or old_authorizee != account_business_name
                        ):
                            state["authorizationAcknowledged"] = False
                        if purpose == 1:
                            state["sections"].pop("powerOfAttorney", None)
                            state["sections"].pop("otherMaterials", None)
                            state["pending"].pop("powerOfAttorney", None)
                            state["pending"].pop("otherMaterials", None)
                        state["revision"] += 1
                    self._json(HTTPStatus.OK, {"success": True})
                    return
                if path == "/api/business-ocr":
                    document_type = int(self.headers.get("X-Document-Type") or "0")
                    result = upload_and_ocr_business_certificate_bytes(
                        client,
                        self._body(MAX_IMAGE_BYTES),
                        self.headers.get_content_type(),
                        document_type,
                    )
                    with lock:
                        state["pending"]["business"] = result
                    self._json(
                        HTTPStatus.OK,
                        {"success": True, "document": result.get("document", {})},
                    )
                    return
                if path == "/api/business":
                    document = self._document()
                    certificate_type = int(document.get("businessCertificateType") or 0)
                    if certificate_type not in (1, 4, 6, 7):
                        raise ValueError
                    start = _date(document.get("businessCertificateValidityPeriodStart"))
                    end = _date(document.get("businessCertificateValidityPeriodEnd"))
                    if end < start:
                        raise ValueError
                    with lock:
                        pending = state["pending"].get("business")
                        existing = state["sections"].get("business")
                        image_required = bool(
                            state["rank"].get("needBusinessCertificateImage")
                        )
                        if image_required and not (
                            isinstance(pending, Mapping) and pending.get("imageUri")
                        ) and not (
                            isinstance(existing, Mapping) and existing.get("imageUri")
                        ):
                            raise ValueError
                        section = {
                            "businessCertificateType": certificate_type,
                            "businessCertificateName": _text(
                                document.get("businessCertificateName")
                            ),
                            "unifiedSocialCreditIdentifier": _text(
                                document.get("unifiedSocialCreditIdentifier"), maximum=64
                            ),
                            "legalPersonName": _text(document.get("legalPersonName")),
                            "businessCertificateValidityPeriodStart": start,
                            "businessCertificateValidityPeriodEnd": end,
                        }
                        image_source = pending if isinstance(pending, Mapping) else existing
                        if isinstance(image_source, Mapping) and image_source.get("imageUri"):
                            section["imageUri"] = image_source["imageUri"]
                            section["imageSuffix"] = image_source["imageSuffix"]
                        material_name = document.get("materialName")
                        material_name_source = str(
                            document.get("materialNameSource") or "auto"
                        )
                        if material_name_source not in ("auto", "manual"):
                            raise ValueError
                        if material_name_source == "auto":
                            material_name = section["businessCertificateName"]
                        state["materialName"] = _text(material_name, maximum=20)
                        state["materialNameSource"] = material_name_source
                        purpose = int(document.get("purpose") or state["purpose"])
                        if purpose not in (1, 2):
                            raise ValueError
                        old_purpose = state.get("purpose")
                        state["purpose"] = purpose
                        if old_purpose != purpose:
                            state["authorizationAcknowledged"] = False
                        if purpose == 1:
                            state["authorizee"] = ""
                            state["sections"].pop("powerOfAttorney", None)
                            state["sections"].pop("otherMaterials", None)
                            state["pending"].pop("powerOfAttorney", None)
                            state["pending"].pop("otherMaterials", None)
                        state["sections"]["business"] = section
                        state["baseSaved"] = True
                        state["checks"].pop("business", None)
                        state["legalAcknowledged"] = False
                        legal_invalidated = False
                        legal = state["sections"].get("legal")
                        if isinstance(legal, Mapping) and legal.get("personName") != section["legalPersonName"]:
                            state["sections"].pop("legal", None)
                            state["pending"].pop("legal", None)
                            legal_invalidated = True
                        state["revision"] += 1
                    self._json(
                        HTTPStatus.OK,
                        {
                            "success": True,
                            "invalidatedLegal": legal_invalidated,
                        },
                    )
                    return
                if path == "/api/person-image":
                    role = str((query.get("role") or [""])[0])
                    side = str((query.get("side") or [""])[0])
                    if role not in PERSON_FILE_TYPES or side not in ("front", "back"):
                        raise ValueError
                    uploaded = upload_qualification_file_bytes(
                        client,
                        self._body(MAX_IMAGE_BYTES),
                        self.headers.get_content_type(),
                    )
                    with lock:
                        pending = state["pending"].setdefault(role, {})
                        pending.setdefault("imageUris", {})[side] = uploaded["imageUri"]
                        pending.setdefault("imageSuffixes", {})[side] = uploaded[
                            "imageSuffix"
                        ]
                    self._json(HTTPStatus.OK, {"success": True})
                    return
                if path == "/api/legal-document":
                    certificate_type = int(
                        (query.get("certificateType") or ["0"])[0]
                    )
                    index = int((query.get("index") or ["-1"])[0])
                    replace_documents = (
                        str((query.get("replace") or ["0"])[0]) == "1"
                    )
                    if (
                        certificate_type not in LEGAL_DOCUMENT_FILE_TYPES
                        or index not in (0, 1)
                    ):
                        raise ValueError
                    uploaded = upload_qualification_file_bytes(
                        client,
                        self._body(MAX_IMAGE_BYTES),
                        self.headers.get_content_type(),
                    )
                    with lock:
                        pending_legal = state["pending"].setdefault("legal", {})
                        if replace_documents:
                            pending_legal["documents"] = {}
                        documents = pending_legal.setdefault("documents", {})
                        documents[index] = uploaded
                    self._json(HTTPStatus.OK, {"success": True})
                    return
                if path == "/api/person-ocr":
                    role = str((query.get("role") or [""])[0])
                    if role not in PERSON_FILE_TYPES:
                        raise ValueError
                    document = self._document()
                    certificate_type = int(document.get("certificateType") or 0)
                    if certificate_type != 0:
                        raise ValueError
                    with lock:
                        pending = state["pending"].get(role)
                        if not isinstance(pending, Mapping):
                            raise ValueError
                        image_uris = pending.get("imageUris")
                        image_suffixes = pending.get("imageSuffixes")
                        front = pending.get("front")
                        back = pending.get("back")
                    if isinstance(image_uris, Mapping) and image_uris.get(
                        "front"
                    ) and image_uris.get("back"):
                        result = ocr_identity_document_images(
                            client,
                            str(image_uris["front"]),
                            str(image_uris["back"]),
                            image_suffixes=(
                                image_suffixes
                                if isinstance(image_suffixes, Mapping)
                                else None
                            ),
                        )
                    else:
                        if not isinstance(front, Mapping) or not isinstance(back, Mapping):
                            raise ValueError
                        result = upload_and_ocr_identity_document_bytes(
                            client,
                            front["data"],
                            front["contentType"],
                            back["data"],
                            back["contentType"],
                        )
                    with lock:
                        state["pending"].setdefault(role, {}).update(result)
                    self._json(
                        HTTPStatus.OK,
                        {"success": True, "person": result.get("person", {})},
                    )
                    return
                if path == "/api/person":
                    document = self._document()
                    role = str(document.get("role") or "")
                    if role not in PERSON_FILE_TYPES:
                        raise ValueError
                    certificate_type = int(document.get("certificateType") or 0)
                    if role == "legal":
                        if certificate_type not in LEGAL_CERTIFICATE_TYPES:
                            raise ValueError
                    elif certificate_type != 0:
                        raise ValueError
                    identity_images_changed = (
                        document.get("identityImagesChanged") is True
                    )
                    documents_changed = document.get("documentsChanged") is True
                    document_count = int(document.get("documentCount") or 0)
                    if document_count < 0 or document_count > 2:
                        raise ValueError
                    skip_empty_legal = (
                        role == "legal"
                        and document.get("skipEmpty") is True
                        and not str(document.get("personIDCard") or "").strip()
                        and not str(document.get("personMobile") or "").strip()
                    )
                    if skip_empty_legal:
                        with lock:
                            state["legalAcknowledged"] = True
                            state["sections"].pop("legal", None)
                            state["pending"].pop("legal", None)
                            state["checks"].pop("legal", None)
                            state["revision"] += 1
                        self._json(HTTPStatus.OK, {"success": True})
                        return
                    mobile_required = _person_requirement(
                        state["rank"], role, "mobile"
                    )
                    image_required = _person_requirement(
                        state["rank"], role, "image"
                    )
                    with lock:
                        pending = state["pending"].get(role)
                        existing = state["sections"].get(role)
                        pending_has_images = _has_identity_image_pair(pending)
                        image_source = (
                            pending
                            if pending_has_images
                            else (
                                None
                                if identity_images_changed
                                else existing
                            )
                        )
                        pending_documents = (
                            pending.get("documents")
                            if isinstance(pending, Mapping)
                            else None
                        )
                        existing_documents = (
                            existing.get("documents")
                            if isinstance(existing, Mapping)
                            else None
                        )
                        if image_required and not _has_identity_image_pair(image_source):
                            raise ValueError
                        business = state["sections"].get("business")
                        person_name = (
                            _legal_person_name(business, document.get("personName"))
                            if role == "legal"
                            else _text(document.get("personName"))
                        )
                        section = {
                            "certificateType": certificate_type,
                            "personName": person_name,
                            "personIDCard": (
                                _id_card(
                                    document.get("personIDCard"),
                                    required=role != "legal",
                                )
                                if certificate_type == 0
                                else _optional_text(
                                    document.get("personIDCard"), maximum=64
                                )
                            ),
                            "personMobile": _mobile(
                                document.get("personMobile"), required=mobile_required
                            ),
                        }
                        if certificate_type == 0:
                            if _has_identity_image_pair(image_source):
                                section["imageUris"] = dict(image_source["imageUris"])
                                section["imageSuffixes"] = dict(
                                    image_source["imageSuffixes"]
                                )
                        else:
                            same_certificate_type = bool(
                                isinstance(existing, Mapping)
                                and int(existing.get("certificateType") or 0)
                                == certificate_type
                            )
                            if documents_changed:
                                document_source = (
                                    pending_documents
                                    if isinstance(pending_documents, Mapping)
                                    else {}
                                )
                            elif same_certificate_type:
                                document_source = existing_documents
                            else:
                                document_source = {}
                            if isinstance(document_source, Mapping):
                                section["documents"] = [
                                    document_source[key]
                                    for key in sorted(document_source)
                                    if int(key) < document_count
                                    if isinstance(document_source[key], Mapping)
                                ]
                            elif isinstance(document_source, list):
                                section["documents"] = list(document_source)
                        state["sections"][role] = section
                        state["pending"].pop(role, None)
                        state["mobileVerifications"].pop(role, None)
                        if role == "legal":
                            state["legalAcknowledged"] = True
                        state["checks"].pop(role, None)
                        if role == "operator" and state.get("sameOperator") is True:
                            state["sections"].pop("responsible", None)
                            state["pending"].pop("responsible", None)
                            state["checks"].pop("responsible", None)
                        state["revision"] += 1
                    self._json(HTTPStatus.OK, {"success": True})
                    return
                if path == "/api/responsible-mode":
                    document = self._document()
                    same_operator = document.get("sameOperator")
                    if not isinstance(same_operator, bool):
                        raise ValueError
                    with lock:
                        operator = state["sections"].get("operator")
                        if not isinstance(operator, Mapping):
                            raise ValueError
                        if same_operator and state["rank"].get(
                            "needResponsibleImage"
                        ) and not _has_identity_image_pair(operator):
                            raise QualificationUploadError(
                                "responsible_reuse_needs_images",
                                "请先为经办人补充身份证正反面，再选择与经办人相同。",
                            )
                        if same_operator and state["rank"].get(
                            "needResponsibleMobile"
                        ) and not operator.get("personMobile"):
                            raise QualificationUploadError(
                                "responsible_reuse_needs_mobile",
                                "请先为经办人补充手机号，再选择与经办人相同。",
                            )
                        state["sameOperator"] = same_operator
                        state["checks"].pop("responsible", None)
                        state["mobileVerifications"].pop("responsible", None)
                        if same_operator:
                            state["sections"].pop("responsible", None)
                            state["pending"].pop("responsible", None)
                        state["revision"] += 1
                    self._json(HTTPStatus.OK, {"success": True})
                    return
                if path == "/api/check":
                    document = self._document()
                    target = str(document.get("target") or "")
                    with lock:
                        frozen_revision = state["revision"]
                        params = _verification_params(state, target)
                    result = check_signature_qualification_information(
                        client, target, params
                    )
                    with lock:
                        if state["revision"] != frozen_revision:
                            self._json(
                                HTTPStatus.CONFLICT,
                                {
                                    "success": False,
                                    "message": "信息已变化，请重新点击校验。",
                                },
                            )
                            return
                        state["checks"][target] = result
                        if target in ("operator", "responsible"):
                            state["mobileVerifications"].pop(target, None)
                        state["revision"] += 1
                        public_check = _public_check(state, target)
                    self._json(
                        HTTPStatus.OK,
                        {
                            "success": True,
                            "target": target,
                            "check": public_check,
                        },
                    )
                    return
                if path == "/api/mobile-code/send":
                    document = self._document()
                    role = str(document.get("role") or "")
                    if role not in ("operator", "responsible"):
                        raise ValueError
                    with lock:
                        if not state["mobileVerificationRequired"]:
                            raise QualificationUploadError(
                                "mobile_verification_not_required",
                                "当前账号无需手机号验证码校验。",
                            )
                        if role == "responsible" and state.get("sameOperator") is True:
                            raise QualificationUploadError(
                                "mobile_verification_not_required",
                                "责任人与经办人相同时复用经办人手机号校验。",
                            )
                        person = state["sections"].get(role)
                        check = state["checks"].get(role)
                        if (
                            not isinstance(person, Mapping)
                            or not person.get("personMobile")
                            or not isinstance(check, Mapping)
                            or not check.get("matched")
                        ):
                            raise QualificationUploadError(
                                "mobile_verification_not_ready",
                                "请先完成当前人员信息校验。",
                            )
                        mobile = str(person["personMobile"])
                    message_id = send_mobile_verification_code(
                        client,
                        mobile,
                        role,
                    )
                    with lock:
                        current_person = state["sections"].get(role)
                        current_check = state["checks"].get(role)
                        if (
                            not isinstance(current_person, Mapping)
                            or current_person.get("personMobile") != mobile
                            or not isinstance(current_check, Mapping)
                            or not current_check.get("matched")
                        ):
                            raise QualificationUploadError(
                                "qualification_draft_changed",
                                "人员信息已变化，请重新获取验证码。",
                            )
                        state["mobileVerifications"][role] = {
                            "mobile": mobile,
                            "messageId": message_id,
                            "verified": False,
                        }
                        state["revision"] += 1
                    self._json(
                        HTTPStatus.OK,
                        {"success": True},
                    )
                    return
                if path == "/api/mobile-code/verify":
                    document = self._document()
                    role = str(document.get("role") or "")
                    submitted_code = _text(document.get("code"), maximum=8)
                    if role not in ("operator", "responsible"):
                        raise ValueError
                    if not re.fullmatch(r"[0-9]{4}", submitted_code):
                        raise QualificationUploadError(
                            "mobile_code_invalid",
                            "请输入 4 位验证码。",
                        )
                    with lock:
                        person = state["sections"].get(role)
                        verification = state["mobileVerifications"].get(role)
                        if (
                            not isinstance(person, Mapping)
                            or not isinstance(verification, Mapping)
                            or verification.get("mobile") != person.get("personMobile")
                        ):
                            raise QualificationUploadError(
                                "mobile_verification_not_ready",
                                "请先获取当前手机号的验证码。",
                            )
                        mobile = str(person["personMobile"])
                    check_mobile_verification_code(
                        client,
                        mobile,
                        submitted_code,
                        role,
                    )
                    with lock:
                        current_person = state["sections"].get(role)
                        verification = state["mobileVerifications"].get(role)
                        if (
                            not isinstance(current_person, Mapping)
                            or current_person.get("personMobile") != mobile
                            or not isinstance(verification, Mapping)
                            or verification.get("mobile") != mobile
                        ):
                            raise QualificationUploadError(
                                "qualification_draft_changed",
                                "人员信息已变化，请重新获取验证码。",
                            )
                        verification["verified"] = True
                        state["revision"] += 1
                    self._json(HTTPStatus.OK, {"success": True})
                    return
                if path == "/api/other-material":
                    index = int((query.get("index") or ["-1"])[0])
                    replace_materials = (
                        str((query.get("replace") or ["0"])[0]) == "1"
                    )
                    if index < 0 or index >= 5:
                        raise ValueError
                    with lock:
                        if state["purpose"] != 2:
                            raise ValueError
                    uploaded = upload_qualification_file_bytes(
                        client,
                        self._body(MAX_IMAGE_BYTES),
                        self.headers.get_content_type(),
                    )
                    with lock:
                        pending_materials = state["pending"].setdefault(
                            "otherMaterials", {}
                        )
                        if replace_materials:
                            pending_materials.clear()
                        pending_materials[index] = uploaded
                    self._json(HTTPStatus.OK, {"success": True})
                    return
                if path == "/api/power-of-attorney":
                    with lock:
                        if not (
                            state["purpose"] == 2
                            and state["rank"].get("needOtherUseCheck")
                        ):
                            raise ValueError
                    uploaded = upload_qualification_file_bytes(
                        client,
                        self._body(MAX_IMAGE_BYTES),
                        self.headers.get_content_type(),
                    )
                    with lock:
                        state["sections"]["powerOfAttorney"] = uploaded
                        state["revision"] += 1
                    self._json(HTTPStatus.OK, {"success": True})
                    return
                if path == "/api/authorization":
                    document = self._document()
                    materials_changed = document.get("otherMaterialsChanged") is True
                    material_count = int(document.get("otherMaterialCount") or 0)
                    if material_count < 0 or material_count > 5:
                        raise ValueError
                    with lock:
                        if state.get("purpose") != 2:
                            raise ValueError
                        if not state.get("authorizee"):
                            raise ValueError
                        pending_materials = state["pending"].get("otherMaterials")
                        existing_materials = state["sections"].get("otherMaterials")
                        if materials_changed:
                            source = (
                                pending_materials
                                if isinstance(pending_materials, Mapping)
                                else {}
                            )
                            materials = [
                                source[index]
                                for index in sorted(source)
                                if int(index) < material_count
                                and isinstance(source[index], Mapping)
                            ]
                        else:
                            materials = (
                                list(existing_materials)
                                if isinstance(existing_materials, list)
                                else []
                            )
                        if materials:
                            state["sections"]["otherMaterials"] = materials
                        else:
                            state["sections"].pop("otherMaterials", None)
                        state["pending"].pop("otherMaterials", None)
                        state["authorizationAcknowledged"] = True
                        state["revision"] += 1
                    self._json(HTTPStatus.OK, {"success": True})
                    return
                if path == "/api/preview":
                    with lock:
                        public = _public_state(state)
                        if not public["readyForPreview"]:
                            self._json(
                                HTTPStatus.CONFLICT,
                                {"success": False, "message": "请先完成必填材料和信息校验；他用资质可能还需要授权委托书"},
                            )
                            return
                        preview = _preview(state)
                    self._json(
                        HTTPStatus.OK, {"success": True, "preview": preview}
                    )
                    return
                if path == "/api/submit":
                    document = self._document()
                    with lock:
                        if (
                            document.get("confirmed") is not True
                            or int(document.get("revision") or -1) != state["revision"]
                            or not _public_state(state)["readyForPreview"]
                        ):
                            self._json(
                                HTTPStatus.CONFLICT,
                                {"success": False, "message": "材料已变化，请重新生成并确认预览"},
                            )
                            return
                        frozen_revision = state["revision"]
                        params = _submission_payload(state)
                    try:
                        result = create_signature_qualification(client, params)
                    except QualificationUploadError as exc:
                        if exc.outcome_unknown:
                            with lock:
                                state["result"] = {
                                    "status": "qualification_submission_outcome_unknown",
                                    "revision": frozen_revision,
                                    "outcomeUnknown": True,
                                    "requestId": exc.request_id,
                                    "logId": exc.log_id,
                                }
                                state["done"] = True
                            self._json(
                                HTTPStatus.BAD_GATEWAY,
                                {
                                    "success": False,
                                    "message": "提交结果暂时无法确认，请勿重复提交；Agent 将停止并保留请求信息",
                                    "error": {
                                        "code": exc.code,
                                        "requestId": exc.request_id,
                                        "logId": exc.log_id,
                                        "outcomeUnknown": True,
                                    },
                                },
                            )
                            return
                        raise
                    with lock:
                        state["result"] = {
                            "status": result["status"],
                            "qualificationId": result["qualificationId"],
                            "requestId": result.get("requestId"),
                            "logId": result.get("logId"),
                            "revision": frozen_revision,
                        }
                        state["done"] = True
                    self._json(
                        HTTPStatus.OK,
                        {
                            "success": True,
                            "qualificationId": result["qualificationId"],
                        },
                    )
                    return
                if path == "/api/abandon":
                    stop("explicit")
                    self._json(HTTPStatus.OK, {"success": True})
                    return
                self.send_error(HTTPStatus.NOT_FOUND)
            except QualificationUploadError as exc:
                failure = {
                    "event": "qualification_failure",
                    "path": path,
                    "code": exc.code,
                    "requestId": exc.request_id,
                    "logId": exc.log_id,
                    "outcomeUnknown": exc.outcome_unknown,
                }
                sys.stderr.write(
                    "QUALIFICATION_FAILURE "
                    + json.dumps(
                        failure,
                        ensure_ascii=False,
                        separators=(",", ":"),
                    )
                    + "\n"
                )
                sys.stderr.flush()
                self._json(
                    HTTPStatus.BAD_REQUEST,
                    {
                        "success": False,
                        "message": str(exc),
                        "error": {
                            "code": exc.code,
                            "requestId": exc.request_id,
                            "logId": exc.log_id,
                            "outcomeUnknown": exc.outcome_unknown,
                        },
                    },
                )
            except (KeyError, TypeError, ValueError, UnicodeError, json.JSONDecodeError):
                self._json(
                    HTTPStatus.BAD_REQUEST,
                    {"success": False, "message": "请检查当前页面中的必填项和格式"},
                )

    server = HTTPServer(("127.0.0.1", 0), Handler)
    server.timeout = 1.0
    url = "http://127.0.0.1:{}/#{}".format(server.server_port, token)
    try:
        display.present(url)
    except Exception:
        server.server_close()
        raise
    try:
        while not state["done"]:
            server.handle_request()
            now = time.monotonic()
            with lock:
                detached_at = state["detachedAt"]
                last_heartbeat = state["lastHeartbeat"]
                last_activity = state["lastActivity"]
            if cancel_event.is_set():
                stop("cancelled")
            elif (
                detached_at is not None
                and now - detached_at >= detach_grace_seconds
            ):
                stop("detached")
            elif now - last_heartbeat >= disconnect_timeout_seconds:
                stop("disconnected")
            elif now - last_activity >= idle_timeout_seconds:
                stop("idle")
    finally:
        server.server_close()
        state["pending"].clear()
        state["sections"].clear()
        state["checks"].clear()
    if state["abandoned"]:
        reason = state["terminationReason"]
        status = {
            "cancelled": "qualification_application_cancelled",
            "detached": "qualification_application_expired",
            "disconnected": "qualification_application_expired",
            "idle": "qualification_application_expired",
        }.get(reason, "qualification_application_abandoned")
        return {"status": status, "reason": reason, "next": "stop"}
    result = state.get("result")
    if not isinstance(result, Mapping):
        raise QualificationUploadError(
            "qualification_submission_failed", "Qualification submission did not finish."
        )
    return dict(result)
