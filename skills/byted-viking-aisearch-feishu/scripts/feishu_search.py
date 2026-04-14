import json
import os
from typing import Any, Dict, List, Optional

import requests


class FeishuDocSearch:
    # 常量定义
    MAX_WIKI_SPACE_PAGES = 10  # 搜索知识库空间时的最大分页数

    def __init__(
        self,
        access_token: Optional[str] = None,
        timeout: int = 30,
    ) -> None:
        self._access_token_override = access_token
        self.timeout = timeout

    def _ok(self, data: Any = None, message: str = "成功") -> Dict[str, Any]:
        res: Dict[str, Any] = {"success": True, "message": message}
        if data is not None:
            res["data"] = data
        return res

    def _error(self, message: str, detail: Any = None) -> Dict[str, Any]:
        res: Dict[str, Any] = {"success": False, "message": message}
        if detail is not None:
            res["error"] = detail
        return res

    def _access_token(self) -> str:
        token = self._access_token_override or os.getenv("LARK_USER_ACCESS_TOKEN")
        if not token:
            raise ValueError("缺少访问凭证: 请设置 LARK_USER_ACCESS_TOKEN 或在初始化时传入 access_token")
        return token

    def _headers(self, content_type: bool = True) -> Dict[str, str]:
        headers: Dict[str, str] = {"Authorization": f"Bearer {self._access_token()}"}
        if content_type:
            headers["Content-Type"] = "application/json; charset=utf-8"
        return headers

    def _request_json(
        self,
        method: str,
        url: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        payload: Optional[Dict[str, Any]] = None,
        content_type: bool = True,
    ) -> Dict[str, Any]:
        try:
            if method.upper() == "GET":
                resp = requests.get(url, headers=self._headers(content_type=False), params=params, timeout=self.timeout)
            elif method.upper() == "POST":
                resp = requests.post(
                    url,
                    headers=self._headers(content_type=content_type),
                    params=params,
                    json=payload,
                    timeout=self.timeout,
                )
            else:
                raise ValueError(f"unsupported method: {method}")
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.HTTPError as e:
            status = e.response.status_code if e.response is not None else 0
            text = e.response.text if e.response is not None else ""
            raise RuntimeError(f"HTTP {status}: {text}", status)
        except requests.exceptions.RequestException as e:
            raise RuntimeError(str(e), 0)

    def _normalize_wiki_obj_type(self, obj_type: Any) -> str:
        mapping = {
            "1": "doc",
            "2": "sheet",
            "8": "docx",
            "11": "slides",
            "22": "bitable",
        }
        key = str(obj_type)
        return mapping.get(key, str(obj_type or ""))

    def _normalize_suite_item(self, item: Dict[str, Any]) -> Dict[str, Any]:
        normalized = dict(item)
        normalized["source"] = "suite_docs"
        return normalized

    def _normalize_wiki_node_item(self, item: Dict[str, Any]) -> Dict[str, Any]:
        obj_type = self._normalize_wiki_obj_type(item.get("obj_type"))
        node_token = item.get("node_id") or item.get("node_token")
        return {
            "docs_token": node_token,
            "docs_type": "wiki",
            "title": item.get("title"),
            "url": item.get("url"),
            "space_id": item.get("space_id"),
            "node_token": node_token,
            "obj_type": obj_type,
            "obj_token": item.get("obj_token"),
            "parent_id": item.get("parent_id"),
            "sort_id": item.get("sort_id"),
            "source": "wiki_nodes",
        }

    def _normalize_wiki_space_item(self, item: Dict[str, Any]) -> Dict[str, Any]:
        space_id = item.get("space_id")
        name = item.get("name") or item.get("space_name")
        return {
            "docs_token": space_id,
            "docs_type": "wiki_space",
            "title": name,
            "space_id": space_id,
            "source": "wiki_spaces",
        }

    def _dedupe_keys(self, item: Dict[str, Any]) -> List[str]:
        keys: List[str] = []
        docs_type = (item.get("docs_type") or "").lower()
        docs_token = item.get("docs_token")
        if docs_type and docs_token:
            keys.append(f"{docs_type}:{docs_token}")
        obj_type = (item.get("obj_type") or "").lower()
        obj_token = item.get("obj_token")
        if obj_type and obj_token:
            keys.append(f"{obj_type}:{obj_token}")
        return keys

    def _merge_items(self, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        merged: List[Dict[str, Any]] = []
        seen = set()
        for item in items:
            keys = self._dedupe_keys(item)
            if keys and any(key in seen for key in keys):
                continue
            merged.append(item)
            for key in keys:
                seen.add(key)
        return merged

    def _runtime_status_code(self, error: Exception) -> int:
        if isinstance(error, RuntimeError) and len(error.args) > 1 and isinstance(error.args[1], int):
            return error.args[1]
        return 0

    def _map_request_error(self, error: Exception, *, scene: str) -> Dict[str, Any]:
        status_code = self._runtime_status_code(error)
        message = str(error)
        permission_message = {
            "wiki_search": "权限不足，请为应用开通 wiki 相关权限",
            "aggregate_search": "权限不足，请为应用开通云文档/表格/多维表格相关权限",
        }.get(scene, "权限不足，请检查应用权限配置")
        default_message = {
            "wiki_search": "wiki 搜索失败",
            "aggregate_search": "搜索失败",
        }.get(scene, "请求失败")
        if status_code == 401 or "Unauthorized" in message:
            return self._error("认证失败，请检查 access_token 是否有效或已过期", {"type": "auth_error", "detail": message})
        if status_code == 403 or "Forbidden" in message:
            return self._error(permission_message, {"type": "permission_denied", "detail": message})
        if "timeout" in message.lower():
            return self._error("请求超时，请稍后重试", {"type": "timeout", "detail": message})
        return self._error(default_message, {"type": "api_error", "detail": message})

    def _build_pagination_warning(self, *, max_pages: int) -> Dict[str, Any]:
        return {
            "pagination_truncated": {
                "message": "知识库空间搜索已达到分页上限，结果可能不完整",
                "max_pages": max_pages,
            }
        }

    def _iter_wiki_spaces_pages(self, *, page_size: int, max_pages: Optional[int] = None) -> Dict[str, Any]:
        collected: List[Dict[str, Any]] = []
        page_token: Optional[str] = None
        page_limit = max(1, max_pages or self.MAX_WIKI_SPACE_PAGES)
        for _ in range(page_limit):
            res = self.list_wiki_spaces(page_size=page_size, page_token=page_token)
            if not res.get("success"):
                return res
            data = res.get("data") or {}
            collected.extend(data.get("items") or [])
            has_more = data.get("has_more", False)
            next_page_token = data.get("page_token")
            if not has_more or not next_page_token:
                return self._ok(
                    {
                        "items": collected,
                        "has_more": has_more,
                        "page_token": next_page_token,
                        "truncated": False,
                    },
                    "获取成功",
                )
            page_token = next_page_token
        return self._ok(
            {
                "items": collected,
                "has_more": True,
                "page_token": page_token,
                "truncated": True,
            },
            "获取成功",
        )

    def _normalize_requested_types(self, types: Optional[List[str]]) -> Dict[str, Any]:
        requested_types = [t.lower() for t in (types or ["doc", "docx", "sheet", "bitable", "wiki", "wiki_space"])]
        return {
            "requested_types": requested_types,
            "suite_types": [t for t in requested_types if t not in ("wiki", "iwiki", "wiki_space")],
            "include_wiki_nodes": "wiki" in requested_types or "iwiki" in requested_types,
            "include_wiki_spaces": "wiki_space" in requested_types,
        }

    def _filter_suite_items_by_types(self, items: List[Dict[str, Any]], suite_types: List[str]) -> List[Dict[str, Any]]:
        allowed_types = set(suite_types)
        return [item for item in items if (item.get("docs_type") or "").lower() in allowed_types]

    def _collect_suite_items(
        self,
        *,
        search_key: str,
        suite_types: List[str],
        fetch_count: int,
        owner_ids: Optional[List[str]],
        chat_ids: Optional[List[str]],
    ) -> Dict[str, Any]:
        if not suite_types:
            return {"items": [], "warnings": {}}
        warnings: Dict[str, Any] = {}
        suite = self._search_suite_docs(
            search_key=search_key,
            count=fetch_count,
            offset=0,
            owner_ids=owner_ids,
            chat_ids=chat_ids,
            docs_types=suite_types,
        )
        if not suite.get("success"):
            warnings["suite_error"] = {
                "message": "文档套件搜索失败",
                "error": suite.get("error"),
            }
            return {"items": [], "warnings": warnings}
        suite_items = suite.get("items") or []
        if suite_items:
            return {"items": suite_items, "warnings": warnings}
        fallback_suite = self._search_suite_docs(
            search_key=search_key,
            count=fetch_count,
            offset=0,
            owner_ids=owner_ids,
            chat_ids=chat_ids,
            docs_types=None,
        )
        if not fallback_suite.get("success"):
            warnings["suite_fallback_error"] = {
                "message": "文档套件回退搜索失败",
                "error": fallback_suite.get("error"),
            }
            return {"items": [], "warnings": warnings}
        return {
            "items": self._filter_suite_items_by_types(fallback_suite.get("items") or [], suite_types),
            "warnings": warnings,
        }

    def _expand_wiki_objects(self, wiki_items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        expanded: List[Dict[str, Any]] = []
        for item in wiki_items:
            obj_type = (item.get("obj_type") or "").lower()
            obj_token = item.get("obj_token")
            if not obj_type or not obj_token:
                continue
            if obj_type in ("doc", "docx", "sheet", "bitable", "base"):
                derived_type = "bitable" if obj_type in ("bitable", "base") else obj_type
                expanded.append(
                    {
                        "docs_type": derived_type,
                        "docs_token": obj_token,
                        "title": item.get("title"),
                        "space_id": item.get("space_id"),
                        "wiki_node_token": item.get("docs_token") or item.get("node_token"),
                        "source": "wiki_nodes_obj",
                    }
                )
        return expanded

    def _collect_wiki_node_items(
        self,
        *,
        search_key: str,
        fetch_count: int,
        space_id: Optional[str],
    ) -> Dict[str, Any]:
        wiki_nodes_res = self.search_wiki_nodes(keyword=search_key, count=fetch_count, offset=0, space_id=space_id)
        if not wiki_nodes_res.get("success"):
            return {
                "items": [],
                "warnings": {
                    "wiki_nodes_error": {
                        "message": wiki_nodes_res.get("message"),
                        "error": wiki_nodes_res.get("error"),
                    }
                },
            }
        wiki_data = wiki_nodes_res.get("data") or {}
        wiki_items = wiki_data.get("items") or []
        return {
            "items": wiki_items + self._expand_wiki_objects(wiki_items),
            "warnings": {},
        }

    def _collect_wiki_space_items(self, *, search_key: str) -> Dict[str, Any]:
        wiki_spaces_res = self.search_wiki_spaces(search_key)
        if not wiki_spaces_res.get("success"):
            return {
                "items": [],
                "warnings": {
                    "wiki_spaces_error": {
                        "message": wiki_spaces_res.get("message"),
                        "error": wiki_spaces_res.get("error"),
                    }
                },
            }
        data = wiki_spaces_res.get("data") or {}
        warnings: Dict[str, Any] = {}
        if data.get("warnings"):
            warnings["wiki_spaces_warning"] = data.get("warnings")
        return {
            "items": data.get("items") or [],
            "warnings": warnings,
        }

    def _merge_and_page_items(self, items: List[Dict[str, Any]], *, offset: int, count: int) -> Dict[str, Any]:
        merged = self._merge_items(items)
        return {
            "total": len(merged),
            "has_more": (offset + count) < len(merged),
            "items": merged[offset: offset + count],
        }

    def _sheet_fetch_sheets(self, url: str) -> Dict[str, Any]:
        try:
            raw = self._request_json("GET", url)
            if raw.get("code", -1) != 0:
                return {"success": False, "error": raw, "items": []}
            return {"success": True, "items": self._extract_sheets_from_response(raw.get("data"))}
        except Exception as e:
            return {"success": False, "error": {"detail": str(e)}, "items": []}

    def _search_suite_docs(
        self,
        search_key: str,
        *,
        count: Optional[int] = None,
        offset: Optional[int] = None,
        owner_ids: Optional[List[str]] = None,
        chat_ids: Optional[List[str]] = None,
        docs_types: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """搜索文档套件，返回统一格式的结果字典，包含 success 字段表示是否成功"""
        url = "https://open.feishu.cn/open-apis/suite/docs-api/search/object"
        body: Dict[str, Any] = {"search_key": search_key}
        if count is not None:
            body["count"] = count
        if offset is not None:
            body["offset"] = offset
        if owner_ids:
            body["owner_ids"] = owner_ids
        if chat_ids:
            body["chat_ids"] = chat_ids
        if docs_types:
            body["docs_types"] = docs_types
        try:
            raw = self._request_json("POST", url, payload=body)
            if raw.get("code", -1) != 0:
                return {
                    "success": False,
                    "error": raw,
                    "items": [],
                    "total": 0,
                    "has_more": False,
                }
            data = raw.get("data") or {}
            items = [self._normalize_suite_item(item) for item in data.get("docs_entities") or []]
            return {
                "success": True,
                "total": data.get("total", len(items)),
                "has_more": data.get("has_more", False),
                "items": items,
            }
        except Exception as e:
            return {
                "success": False,
                "error": {"detail": str(e)},
                "items": [],
                "total": 0,
                "has_more": False,
            }

    def list_wiki_spaces(
        self,
        *,
        page_size: int = 20,
        page_token: Optional[str] = None,
    ) -> Dict[str, Any]:
        try:
            url = "https://open.feishu.cn/open-apis/wiki/v2/spaces"
            params: Dict[str, Any] = {"page_size": page_size}
            if page_token:
                params["page_token"] = page_token
            raw = self._request_json("GET", url, params=params)
            if raw.get("code", -1) != 0:
                return self._error("获取知识库空间列表失败", raw)
            data = raw.get("data") or {}
            items = [self._normalize_wiki_space_item(item) for item in data.get("items") or []]
            return self._ok(
                {
                    "items": items,
                    "has_more": data.get("has_more", False),
                    "page_token": data.get("page_token"),
                },
                "获取成功",
            )
        except Exception as e:
            return self._error("获取知识库空间列表失败", {"detail": str(e)})

    def search_wiki_spaces(
        self,
        keyword: str,
        *,
        page_size: int = 50,
        max_pages: Optional[int] = None,
    ) -> Dict[str, Any]:
        if not keyword or not keyword.strip():
            return self._error("keyword 不能为空")
        page_limit = max(1, max_pages or self.MAX_WIKI_SPACE_PAGES)
        res = self._iter_wiki_spaces_pages(page_size=page_size, max_pages=page_limit)
        if not res.get("success"):
            return res
        data = res.get("data") or {}
        kw = keyword.strip().lower()
        matched = [it for it in (data.get("items") or []) if kw in (it.get("title") or "").lower()]
        payload: Dict[str, Any] = {
            "total": len(matched),
            "has_more": data.get("has_more", False),
            "items": matched,
        }
        if data.get("page_token"):
            payload["page_token"] = data.get("page_token")
        if data.get("truncated"):
            payload["warnings"] = self._build_pagination_warning(max_pages=page_limit)
        return self._ok(payload, "搜索成功")

    def list_wiki_space_nodes(
        self,
        space_id: str,
        *,
        parent_node_token: Optional[str] = None,
        page_size: int = 20,
        page_token: Optional[str] = None,
    ) -> Dict[str, Any]:
        if not space_id or not space_id.strip():
            return self._error("space_id 不能为空")
        try:
            url = f"https://open.feishu.cn/open-apis/wiki/v2/spaces/{space_id}/nodes"
            params: Dict[str, Any] = {"page_size": page_size}
            if page_token:
                params["page_token"] = page_token
            if parent_node_token:
                params["parent_node_token"] = parent_node_token
            raw = self._request_json("GET", url, params=params)
            if raw.get("code", -1) != 0:
                return self._error("获取知识库空间子节点失败", raw)
            data = raw.get("data") or {}
            items = [self._normalize_wiki_node_item(it) for it in data.get("items") or []]
            return self._ok(
                {
                    "items": items,
                    "has_more": data.get("has_more", False),
                    "page_token": data.get("page_token"),
                },
                "获取成功",
            )
        except Exception as e:
            return self._error("获取知识库空间子节点失败", {"detail": str(e)})

    def search_wiki_nodes(
        self,
        keyword: str,
        *,
        count: Optional[int] = None,
        offset: Optional[int] = None,
        space_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        if not keyword or not keyword.strip():
            return self._error("keyword 不能为空")
        body: Dict[str, Any] = {"query": keyword}
        if count is not None:
            body["count"] = count
        if offset is not None:
            body["offset"] = offset
        if space_id:
            body["space_id"] = space_id
        try:
            raw = self._request_json("POST", "https://open.feishu.cn/open-apis/wiki/v2/nodes/search", payload=body)
            if raw.get("code", -1) != 0:
                return self._error("飞书 wiki 搜索接口返回错误", raw)
            data = raw.get("data") or {}
            items = [self._normalize_wiki_node_item(item) for item in data.get("items") or []]
            return self._ok(
                {
                    "total": data.get("total", len(items)),
                    "has_more": data.get("has_more", False),
                    "items": items,
                },
                "搜索成功",
            )
        except Exception as e:
            return self._map_request_error(e, scene="wiki_search")

    def search_items(
        self,
        search_key: str,
        *,
        count: int = 10,
        offset: int = 0,
        types: Optional[List[str]] = None,
        owner_ids: Optional[List[str]] = None,
        chat_ids: Optional[List[str]] = None,
        space_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        if not search_key or not search_key.strip():
            return self._error("search_key 不能为空")
        type_config = self._normalize_requested_types(types)
        fetch_count = min(50, max(count + offset, count))
        try:
            items: List[Dict[str, Any]] = []
            warnings: Dict[str, Any] = {}

            suite_result = self._collect_suite_items(
                search_key=search_key,
                suite_types=type_config["suite_types"],
                fetch_count=fetch_count,
                owner_ids=owner_ids,
                chat_ids=chat_ids,
            )
            items.extend(suite_result["items"])
            warnings.update(suite_result["warnings"])

            if type_config["include_wiki_nodes"]:
                wiki_node_result = self._collect_wiki_node_items(
                    search_key=search_key,
                    fetch_count=fetch_count,
                    space_id=space_id,
                )
                items.extend(wiki_node_result["items"])
                warnings.update(wiki_node_result["warnings"])

            if type_config["include_wiki_spaces"]:
                wiki_space_result = self._collect_wiki_space_items(search_key=search_key)
                items.extend(wiki_space_result["items"])
                warnings.update(wiki_space_result["warnings"])

            data = self._merge_and_page_items(items, offset=offset, count=count)
            if warnings:
                data["warnings"] = warnings
            return self._ok(data, "搜索成功")
        except Exception as e:
            return self._map_request_error(e, scene="aggregate_search")

    def search_docs(
        self,
        search_key: str,
        count: Optional[int] = None,
        offset: Optional[int] = None,
        owner_ids: Optional[List[str]] = None,
        chat_ids: Optional[List[str]] = None,
        docs_types: Optional[List[str]] = ["doc", "docx", "sheet", "bitable", "wiki"],
    ) -> Dict[str, Any]:
        """
        文档搜索
        
        在飞书中按关键词搜索文档
        
        Args:
            search_key: 搜索关键词，必填
            count: 返回数量，范围 [0, 50]，默认不指定
            offset: 偏移量，需满足 offset + count < 200，默认不指定
            owner_ids: 所有者 Open ID 列表，用于按所有者筛选
            chat_ids: 文件所在群 ID 列表，用于按群筛选
            docs_types: 文档类型枚举，默认 ["doc", "docx", "sheet", "bitable", "wiki"]
                        可选值: doc, docx, sheet, bitable, wiki
        
        Returns:
            {
              "success": true,
              "message": "搜索成功",
              "data": {
                "total": 2,
                "has_more": false,
                "items": [
                  {
                    "docs_token": "...", 
                    "docs_type": "doc", 
                    "title": "xxx", 
                    "owner_id": "ou_..."
                  }
                ]
              }
            }
        
        错误返回示例:
            {
              "success": false,
              "message": "认证失败，请检查 access_token 是否有效或已过期",
              "error": {"type": "auth_error", "detail": "..."}
            }
        """
        c = count if count is not None else 10
        o = offset if offset is not None else 0
        types = [t.lower() for t in (docs_types or ["doc", "docx", "sheet", "bitable", "wiki"])]
        include_wiki = "wiki" in types or "iwiki" in types
        include_suite = [t for t in types if t not in ("wiki", "iwiki")]
        result = self.search_items(
            search_key=search_key,
            count=c,
            offset=o,
            types=include_suite + (["wiki"] if include_wiki else []),
            owner_ids=owner_ids,
            chat_ids=chat_ids,
        )
        return result

    def get_docx_raw_content(self, document_id: str) -> Dict[str, Any]:
        try:
            url = f"https://open.feishu.cn/open-apis/docx/v1/documents/{document_id}/raw_content"
            raw = self._request_json("GET", url)
            if raw.get("code", -1) == 0:
                return self._ok({"content": raw.get("data", {}).get("content", "")}, "获取成功")
            return self._error("获取 docx 原文失败", raw)
        except Exception as e:
            return self._error("获取 docx 原文失败", {"detail": str(e)})

    def get_doc_raw_content(self, document_id: str) -> Dict[str, Any]:
        try:
            url = f"https://open.feishu.cn/open-apis/docs/v2/documents/{document_id}/raw_content"
            raw = self._request_json("GET", url)
            if raw.get("code", -1) == 0:
                return self._ok({"content": raw.get("data", {}).get("content", "")}, "获取成功")
            return self._error("获取 doc 原文失败", raw)
        except Exception as e:
            return self._error("获取 doc 原文失败", {"detail": str(e)})

    def get_wiki_node(self, node_token: str) -> Dict[str, Any]:
        try:
            url = f"https://open.feishu.cn/open-apis/wiki/v2/spaces/get_node?token={node_token}"
            raw = self._request_json("GET", url)
            if raw.get("code", -1) != 0:
                return self._error("获取 wiki 节点失败", raw)
            node = (raw.get("data") or {}).get("node") or {}
            data = {
                "node_token": node.get("node_token"),
                "title": node.get("title"),
                "obj_type": self._normalize_wiki_obj_type(node.get("obj_type")),
                "obj_token": node.get("obj_token"),
                "node_type": node.get("node_type"),
                "space_id": node.get("space_id"),
                "creator": node.get("creator"),
                "owner": node.get("owner"),
            }
            return self._ok(data, "获取成功")
        except Exception as e:
            return self._error("获取 wiki 节点失败", {"detail": str(e)})

    def _sheet_guess_range(self, sheet_prefix: str, max_rows: int, max_cols: int) -> str:
        cols = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        col = cols[min(max_cols, len(cols)) - 1] if max_cols > 0 else "A"
        row = max(1, max_rows)
        return f"{sheet_prefix}!A1:{col}{row}"

    def _sheet_values_to_tsv(self, values: List[List[Any]]) -> str:
        lines: List[str] = []
        for row in values:
            parts = []
            for v in row:
                if v is None:
                    parts.append("")
                else:
                    parts.append(str(v))
            lines.append("\t".join(parts))
        return "\n".join(lines)

    def _parse_sheet_info(self, sheet_data: Any) -> Optional[Dict[str, str]]:
        """从 sheet 数据中提取 sheet_id 和 title，返回 None 如果数据无效"""
        if not isinstance(sheet_data, dict):
            return None
        props = sheet_data.get("properties") or {}
        title = sheet_data.get("title") or sheet_data.get("sheet_title") or props.get("title")
        sheet_id = (
            sheet_data.get("sheet_id")
            or sheet_data.get("sheetId")
            or props.get("sheet_id")
            or props.get("sheetId")
        )
        if title and sheet_id:
            return {"sheet_id": str(sheet_id), "title": str(title)}
        return None

    def _extract_sheets_from_response(self, response_data: Dict[str, Any]) -> List[Dict[str, str]]:
        """从 API 响应数据中提取 sheets 列表"""
        sheets_out: List[Dict[str, str]] = []
        data = response_data or {}
        # 支持多种可能的字段名
        sheets = data.get("sheets") or data.get("sheet_list") or data.get("items") or []
        if isinstance(sheets, list):
            for s in sheets:
                sheet_info = self._parse_sheet_info(s)
                if sheet_info:
                    sheets_out.append(sheet_info)
        return sheets_out

    def _sheet_list_sheets(self, spreadsheet_token: str) -> Dict[str, Any]:
        """获取电子表格的 sheet 列表，尝试多个 API 端点"""
        meta_url = f"https://open.feishu.cn/open-apis/sheets/v3/spreadsheets/{spreadsheet_token}/metainfo"
        query_url = f"https://open.feishu.cn/open-apis/sheets/v3/spreadsheets/{spreadsheet_token}/sheets/query"
        metainfo = self._sheet_fetch_sheets(meta_url)
        if metainfo.get("success") and metainfo.get("items"):
            return {"success": True, "items": metainfo.get("items") or []}
        query = self._sheet_fetch_sheets(query_url)
        warnings: Dict[str, Any] = {}
        if not metainfo.get("success"):
            warnings["metainfo_error"] = metainfo.get("error")
        if query.get("success"):
            result: Dict[str, Any] = {"success": True, "items": query.get("items") or []}
            if warnings:
                result["warnings"] = warnings
            return result
        errors: Dict[str, Any] = {}
        if not metainfo.get("success"):
            errors["metainfo_error"] = metainfo.get("error")
        if not query.get("success"):
            errors["query_error"] = query.get("error")
        return {"success": False, "items": [], "error": errors}

    def _sheet_map_range(self, a1: str, sheets: List[Dict[str, str]]) -> List[str]:
        s = (a1 or "").strip()
        if "!" not in s:
            return [s]
        prefix, rest = s.split("!", 1)
        prefix = prefix.strip()
        rest = rest.strip()
        if not prefix or not rest:
            return [s]
        by_id = {it.get("sheet_id"): it for it in sheets if it.get("sheet_id")}
        by_title = {it.get("title"): it for it in sheets if it.get("title")}
        candidates: List[str] = []
        if prefix in by_id:
            candidates.append(s)
        if prefix in by_title and by_title[prefix].get("sheet_id"):
            candidates.append(f"{by_title[prefix]['sheet_id']}!{rest}")
        if prefix not in by_id and prefix not in by_title:
            candidates.append(s)
        seen = set()
        uniq: List[str] = []
        for c in candidates:
            if c and c not in seen:
                seen.add(c)
                uniq.append(c)
        return uniq

    def fetch_sheet_content(
        self,
        spreadsheet_token: str,
        *,
        range_a1: Optional[str] = None,
        max_rows: int = 100,
        max_cols: int = 26,
    ) -> Dict[str, Any]:
        try:
            sheets_result = self._sheet_list_sheets(spreadsheet_token)
            if not sheets_result.get("success"):
                return self._error("读取 sheet 数据失败", sheets_result.get("error"))
            sheets = sheets_result.get("items") or []
            warnings = dict(sheets_result.get("warnings") or {})
            first = sheets[0] if sheets else {}
            sheet_id = first.get("sheet_id") or "Sheet1"
            title = first.get("title") or "Sheet1"
            if range_a1:
                candidate_ranges = self._sheet_map_range(range_a1, sheets)
            else:
                candidate_ranges = [
                    self._sheet_guess_range(sheet_id, max_rows=max_rows, max_cols=max_cols),
                    self._sheet_guess_range(title, max_rows=max_rows, max_cols=max_cols),
                ]
            values_url = f"https://open.feishu.cn/open-apis/sheets/v2/spreadsheets/{spreadsheet_token}/values_batch_get"
            last_raw: Optional[Dict[str, Any]] = None
            for a1 in candidate_ranges:
                raw = self._request_json("GET", values_url, params={"ranges": a1})
                last_raw = raw
                if raw.get("code", -1) != 0:
                    continue
                value_ranges = (raw.get("data") or {}).get("valueRanges") or []
                values = []
                if isinstance(value_ranges, list) and value_ranges:
                    values = (value_ranges[0] or {}).get("values") or []
                content = self._sheet_values_to_tsv(values) if isinstance(values, list) else ""
                data: Dict[str, Any] = {
                    "spreadsheet_token": spreadsheet_token,
                    "range_a1": a1,
                    "content": content,
                }
                if warnings:
                    data["warnings"] = warnings
                return self._ok(data, "获取成功")
            return self._error("读取 sheet 数据失败", last_raw or {"detail": "unknown"})
        except Exception as e:
            return self._error("读取 sheet 数据失败", {"detail": str(e)})

    def list_bitable_tables(
        self,
        app_token: str,
        *,
        page_size: int = 20,
        page_token: Optional[str] = None,
    ) -> Dict[str, Any]:
        try:
            url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{app_token}/tables"
            params: Dict[str, Any] = {"page_size": page_size}
            if page_token:
                params["page_token"] = page_token
            raw = self._request_json("GET", url, params=params)
            if raw.get("code", -1) != 0:
                return self._error("获取数据表列表失败", raw)
            data = raw.get("data") or {}
            return self._ok(
                {
                    "items": data.get("items") or [],
                    "has_more": data.get("has_more", False),
                    "page_token": data.get("page_token"),
                },
                "获取成功",
            )
        except Exception as e:
            return self._error("获取数据表列表失败", {"detail": str(e)})

    def search_bitable_records(
        self,
        app_token: str,
        table_id: str,
        *,
        field_names: Optional[List[str]] = None,
        page_size: int = 20,
        page_token: Optional[str] = None,
        filter_info: Optional[Dict[str, Any]] = None,
        sort: Optional[List[Dict[str, Any]]] = None,
        automatic_fields: bool = False,
    ) -> Dict[str, Any]:
        try:
            url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records/search"
            params: Dict[str, Any] = {"page_size": page_size}
            if page_token:
                params["page_token"] = page_token
            body: Dict[str, Any] = {"automatic_fields": automatic_fields}
            if field_names:
                body["field_names"] = field_names
            if filter_info:
                body["filter"] = filter_info
            if sort:
                body["sort"] = sort
            raw = self._request_json("POST", url, params=params, payload=body)
            if raw.get("code", -1) != 0:
                return self._error("查询记录失败", raw)
            data = raw.get("data") or {}
            return self._ok(
                {
                    "items": data.get("items") or [],
                    "has_more": data.get("has_more", False),
                    "page_token": data.get("page_token"),
                    "total": data.get("total"),
                },
                "获取成功",
            )
        except Exception as e:
            return self._error("查询记录失败", {"detail": str(e)})

    def fetch_bitable_content(
        self,
        app_token: str,
        *,
        table_id: Optional[str] = None,
        page_size: int = 20,
        page_token: Optional[str] = None,
    ) -> Dict[str, Any]:
        tables_res = self.list_bitable_tables(app_token, page_size=100)
        if not tables_res.get("success"):
            return tables_res
        tables_data = tables_res.get("data") or {}
        tables = tables_data.get("items") or []
        chosen_table_id = table_id
        if not chosen_table_id and tables:
            chosen_table_id = (tables[0] or {}).get("table_id")
        records: Optional[Dict[str, Any]] = None
        if chosen_table_id:
            records = self.search_bitable_records(
                app_token=app_token,
                table_id=chosen_table_id,
                page_size=min(500, max(1, page_size)),
                page_token=page_token,
            )
        payload: Dict[str, Any] = {
            "app_token": app_token,
            "tables": tables,
            "selected_table_id": chosen_table_id,
        }
        warnings: Dict[str, Any] = {}
        if records is not None and records.get("success"):
            payload["records"] = records.get("data")
        if records is not None and not records.get("success"):
            warnings["records_error"] = {
                "message": records.get("message"),
                "error": records.get("error"),
            }
        content = json.dumps(payload, ensure_ascii=False, indent=2)
        data: Dict[str, Any] = {"content": content}
        if warnings:
            data["warnings"] = warnings
            return self._ok(data, "部分成功：已获取数据表列表，但记录样本读取失败")
        return self._ok(data, "获取成功")

    def _parse_int_param(self, value: Any, default: int) -> int:
        """安全地将参数转换为整数，处理 None 和非数字字符串的情况"""
        if value is None:
            return default
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    def fetch_raw_content(self, docs_type: str, docs_token: str, **kwargs: Any) -> Dict[str, Any]:
        t = (docs_type or "").lower()
        if t in ("docx", "doc"):
            if t == "docx":
                return self.get_docx_raw_content(docs_token)
            return self.get_doc_raw_content(docs_token)
        if t in ("sheet",):
            return self.fetch_sheet_content(
                docs_token,
                range_a1=kwargs.get("range_a1"),
                max_rows=self._parse_int_param(kwargs.get("max_rows"), 100),
                max_cols=self._parse_int_param(kwargs.get("max_cols"), 26),
            )
        if t in ("bitable", "base"):
            return self.fetch_bitable_content(
                docs_token,
                table_id=kwargs.get("table_id"),
                page_size=self._parse_int_param(kwargs.get("page_size"), 20),
                page_token=kwargs.get("page_token"),
            )
        if t in ("wiki", "iwiki"):
            node_res = self.get_wiki_node(docs_token)
            if not node_res.get("success"):
                return node_res
            node = node_res.get("data") or {}
            obj_type = (node.get("obj_type") or "").lower()
            obj_token = node.get("obj_token")
            if obj_type in ("doc", "docx") and obj_token:
                return self.fetch_raw_content(obj_type, obj_token)
            if obj_type in ("sheet",) and obj_token:
                return self.fetch_raw_content("sheet", obj_token, **kwargs)
            if obj_type in ("bitable", "base") and obj_token:
                return self.fetch_raw_content("bitable", obj_token, **kwargs)
            content = json.dumps(node, ensure_ascii=False, indent=2)
            return self._ok({"content": content}, "获取 wiki 节点信息成功")
        if t in ("wiki_space", "wiki-space"):
            space_nodes = self.list_wiki_space_nodes(
                docs_token,
                parent_node_token=kwargs.get("parent_node_token"),
                page_size=self._parse_int_param(kwargs.get("page_size"), 20),
                page_token=kwargs.get("page_token"),
            )
            if not space_nodes.get("success"):
                return space_nodes
            content = json.dumps(space_nodes.get("data"), ensure_ascii=False, indent=2)
            return self._ok({"content": content}, "获取成功")
        return self._error("不支持的 docs_type，仅支持 doc、docx、sheet、bitable、wiki、wiki_space")
