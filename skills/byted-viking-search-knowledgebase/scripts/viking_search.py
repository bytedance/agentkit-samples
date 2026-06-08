#!/usr/bin/env python3
"""Viking 知识库检索

支持三种用法：

1) 意图明确 + 已知目标知识库：
   - 模型 在路由时明确知道目标知识库，通过 --resource-id 或 --name 指定。
   - 直接对指定库执行 search，返回精准检索结果。

2) 意图明确 + 未知目标知识库（需推理路由）：
   - 用户有明确问题，但不知道该查哪个库。
   - 模型需先调用 info 动作获取所有有权限库的 collection_name 和 description，
     结合用户问题推理出目标库后，再调用 search 精准检索。

3) 意图不明确：多库并行检索（auto 模式）：
   - 用户的问题无法判断具体目标，或推理后仍不确定。
   - 调用 auto 模式，脚本对所有有权限库并发执行轻量级 search，
     直接返回各库的检索结果列表，供模型做最终决策。

鉴权方式：API Gateway 代理网关（Bearer apikey）
  - DATABASE_VIKING_APIG_URL: 代理网关 URL（形如 http(s)://xxxx.apigateway-...volceapi.com）
  - DATABASE_VIKING_APIG_KEY: 代理网关 API Key

有权限知识库列表：
  - DATABASE_VIKING_COLLECTION: 逗号分隔的 knowledge collection resource_id 列表

权限管控：
  - info / search 仅允许访问 DATABASE_VIKING_COLLECTION 中的知识库；
  - 通过 --name 定位时，仅在允许列表内解析 collection_name，不对外部库发起 API 查询。

依赖：Python 3.7+、requests
"""

import argparse
import json
import os
import re
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

SEARCH_KNOWLEDGE_PATH = "/api/knowledge/collection/search_knowledge"
COLLECTION_INFO_PATH = "/api/knowledge/collection/info"

ALLOWED_COLLECTION_IDS_ENV = "DATABASE_VIKING_COLLECTION"
PERMISSION_DENIED_MSG = "没有权限访问当前知识库数据源"


def _parse_csv_list(raw: str):
    if not raw:
        return []
    return [part.strip() for part in raw.split(",") if part.strip()]


def _normalize_text(text: str):
    return re.sub(r"\s+", "", (text or "")).lower()


def _truncate(text: str, max_len: int):
    if text is None:
        return ""
    if len(text) <= max_len:
        return text
    return text[: max_len - 1] + "…"


class ApigKnowledgeClient:
    """通过 APIG 代理网关访问 Viking 知识库 API。"""

    def __init__(self, *, apig_url: str, apig_key: str):
        if not apig_url:
            raise ValueError("apig_url is required")
        if not apig_key:
            raise ValueError("apig_key is required")
        self.apig_url = apig_url.rstrip("/")
        self.apig_key = apig_key

    def _post(self, path: str, payload_dict: dict):
        url = f"{self.apig_url}{path}"
        payload = json.dumps(payload_dict, ensure_ascii=False)
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.apig_key}",
        }

        response = requests.post(url, headers=headers, data=payload.encode("utf-8"))
        response.raise_for_status()
        return response.json()

    def collection_info(
        self,
        *,
        resource_id: str = "",
        name: str = "",
        project: str = "",
    ):
        payload = {}
        if resource_id:
            payload["resource_id"] = resource_id
        if name:
            payload["name"] = name
        if project:
            payload["project"] = project
        return self._post(COLLECTION_INFO_PATH, payload)

    def search_knowledge(
        self,
        *,
        query: str,
        name: str = "",
        project: str = "",
        resource_id: str = "",
        limit: int = 10,
        image_query: str = "",
        query_param=None,
        dense_weight: float = 0.5,
        pre_processing=None,
        post_processing=None,
        pipeline_name: str = "",
    ):
        payload = {
            "query": query,
            "limit": limit,
            "dense_weight": dense_weight,
        }
        if name:
            payload["name"] = name
        if project:
            payload["project"] = project
        if resource_id:
            payload["resource_id"] = resource_id
        if image_query:
            payload["image_query"] = image_query
        if query_param:
            payload["query_param"] = query_param
        if pre_processing:
            payload["pre_processing"] = pre_processing
        if post_processing:
            payload["post_processing"] = post_processing
        if pipeline_name:
            payload["pipeline_name"] = pipeline_name

        return self._post(SEARCH_KNOWLEDGE_PATH, payload)


def _extract_top_chunks(search_resp: dict, top_k: int):
    result_list = (
        (search_resp or {}).get("data", {}) or {}
    ).get("result_list") or []

    chunks = []
    for item in result_list[:top_k]:
        doc_info = item.get("doc_info") or {}
        chunks.append(
            {
                "score": item.get("score"),
                "rerank_score": item.get("rerank_score"),
                "content": item.get("content"),
                "chunk_title": item.get("chunk_title"),
                "chunk_id": item.get("chunk_id"),
                "doc_id": doc_info.get("doc_id"),
                "doc_name": doc_info.get("doc_name"),
                "doc_type": doc_info.get("doc_type"),
                "url": doc_info.get("url"),
            }
        )
    return chunks


def _load_allowed_collection_ids(args):
    raw = args.allowed_collection_ids or os.getenv(ALLOWED_COLLECTION_IDS_ENV, "")
    return _parse_csv_list(raw)


def _require_allowed_collection_ids(allowed_ids: list):
    if not allowed_ids:
        raise SystemExit(PERMISSION_DENIED_MSG)


def _assert_resource_id_allowed(resource_id: str, allowed_set: set):
    if not resource_id or resource_id not in allowed_set:
        raise SystemExit(PERMISSION_DENIED_MSG)


def _extract_resource_id_from_response(resp: dict):
    data = (resp or {}).get("data") or {}
    return (data.get("resource_id") or "").strip()


def _assert_response_collection_allowed(resp: dict, allowed_set: set):
    resource_id = _extract_resource_id_from_response(resp)
    if resource_id and resource_id not in allowed_set:
        raise SystemExit(PERMISSION_DENIED_MSG)


def _find_allowed_collection_by_name(
    client: ApigKnowledgeClient,
    allowed_ids: list,
    *,
    name: str,
    project: str,
    max_workers: int,
):
    """仅在 DATABASE_VIKING_COLLECTION 范围内按 name+project 解析，避免对外部库发起查询。"""
    target_name = _normalize_text(name)
    target_project = (project or "default").strip()

    for item in _fetch_collections_info(client, allowed_ids, max_workers=max_workers):
        if item.get("error"):
            continue
        if _normalize_text(item.get("collection_name")) != target_name:
            continue
        item_project = (item.get("project") or "default").strip()
        if item_project != target_project:
            continue
        return item

    raise SystemExit(PERMISSION_DENIED_MSG)


def _resolve_authorized_target(
    *,
    client: ApigKnowledgeClient,
    resource_id: str,
    name: str,
    project: str,
    allowed_ids: list,
    allowed_set: set,
    max_workers: int,
):
    _require_allowed_collection_ids(allowed_ids)

    if resource_id:
        _assert_resource_id_allowed(resource_id, allowed_set)
        return resource_id, None

    if name:
        matched = _find_allowed_collection_by_name(
            client,
            allowed_ids,
            name=name,
            project=project,
            max_workers=max_workers,
        )
        resolved_id = (matched.get("resource_id") or "").strip()
        _assert_resource_id_allowed(resolved_id, allowed_set)
        return resolved_id, matched.get("raw")

    raise SystemExit(PERMISSION_DENIED_MSG)


def _fetch_collections_info(client: ApigKnowledgeClient, resource_ids: list, *, max_workers: int = 8):
    results = []

    def fetch(rid: str):
        resp = client.collection_info(resource_id=rid)
        if (resp or {}).get("code") != 0:
            raise RuntimeError(f"collection_info failed: {resp}")
        data = resp.get("data") or {}
        return {
            "resource_id": data.get("resource_id") or rid,
            "collection_name": data.get("collection_name") or "",
            "description": data.get("description") or "",
            "project": data.get("project") or "",
            "raw": resp,
        }

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_map = {executor.submit(fetch, rid): rid for rid in resource_ids}
        for future in as_completed(future_map):
            rid = future_map[future]
            try:
                results.append(future.result())
            except Exception as exc:
                results.append(
                    {
                        "resource_id": rid,
                        "collection_name": "",
                        "description": "",
                        "project": "",
                        "error": str(exc),
                    }
                )

    results.sort(key=lambda x: x.get("collection_name") or x.get("resource_id"))
    return results


def _search_one_collection(client: ApigKnowledgeClient, *, resource_id: str, query: str, limit: int):
    resp = client.search_knowledge(query=query, resource_id=resource_id, limit=limit)
    if (resp or {}).get("code") != 0:
        raise RuntimeError(f"search_knowledge failed: {resp}")
    return resp


def _run_multi_search(client: ApigKnowledgeClient, *, collections: list, query: str, limit: int, top_k: int, max_workers: int):
    results = []

    def search(item: dict):
        rid = item.get("resource_id")
        resp = _search_one_collection(client, resource_id=rid, query=query, limit=limit)
        return {
            **item,
            "search": resp,
            "top_chunks": _extract_top_chunks(resp, top_k),
        }

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_map = {executor.submit(search, item): item for item in collections if item.get("resource_id")}
        for future in as_completed(future_map):
            item = future_map[future]
            try:
                results.append(future.result())
            except Exception as exc:
                results.append({**item, "error": str(exc)})

    results.sort(key=lambda x: x.get("collection_name") or x.get("resource_id"))
    return results


def main():
    parser = argparse.ArgumentParser(description="Viking 知识库检索（代理网关）")

    parser.add_argument(
        "--action",
        choices=["search", "info", "auto"],
        default="search",
        help="search: 单库检索；info: 查看知识库详情；auto: 自动路由/多库并行检索",
    )

    parser.add_argument("--query", default="", help="搜索查询文本（search/auto 必填）")
    parser.add_argument("--name", default="", help="知识库名称（可选）")
    parser.add_argument("--project", default=os.getenv("DATABASE_VIKING_PROJECT"), help="项目名称（默认读取 DATABASE_VIKING_PROJECT，使用 --name 检索时必填）")
    parser.add_argument("--resource-id", default="", help="知识库 resource_id（推荐使用，auto模式下作为明确路由的标志）")

    parser.add_argument("--limit", type=int, default=10, help="search_knowledge 返回结果数量")
    parser.add_argument("--top-k", type=int, default=3, help="summary 提取的 top chunk 数")

    parser.add_argument(
        "--allowed-collection-ids",
        default="",
        help=f"有权限的知识库 resource_id 列表（逗号分隔）。默认读取 env {ALLOWED_COLLECTION_IDS_ENV}",
    )

    parser.add_argument(
        "--max-workers",
        type=int,
        default=8,
        help="并发 worker 数（auto 多库检索/拉取 info 时使用）",
    )

    parser.add_argument(
        "--apig-url",
        default=os.getenv("DATABASE_VIKING_APIG_URL"),
        help="代理网关 URL（默认读取环境变量 DATABASE_VIKING_APIG_URL）",
    )
    parser.add_argument(
        "--apig-key",
        default=os.getenv("DATABASE_VIKING_APIG_KEY"),
        help="代理网关 API Key（默认读取环境变量 DATABASE_VIKING_APIG_KEY）",
    )

    args = parser.parse_args()

    if not args.apig_url or not args.apig_key:
        raise SystemExit(
            "检测到环境配置缺失：请联系管理员在执行环境中补充 DATABASE_VIKING_APIG_URL 和 DATABASE_VIKING_APIG_KEY 等环境变量。"
        )

    client = ApigKnowledgeClient(apig_url=args.apig_url, apig_key=args.apig_key)

    allowed_ids = _load_allowed_collection_ids(args)
    allowed_set = set(allowed_ids)

    if args.action == "info":
        if not args.resource_id and not args.name:
            raise SystemExit("info action requires --resource-id or --name")
        if not args.resource_id and args.name and not args.project:
            raise SystemExit("when using --name, --project (or env DATABASE_VIKING_PROJECT) is required")

        target_rid, cached_resp = _resolve_authorized_target(
            client=client,
            resource_id=args.resource_id,
            name=args.name,
            project=args.project,
            allowed_ids=allowed_ids,
            allowed_set=allowed_set,
            max_workers=args.max_workers,
        )
        resp = cached_resp or client.collection_info(resource_id=target_rid)
        _assert_response_collection_allowed(resp, allowed_set)
        print(json.dumps(resp, ensure_ascii=False, indent=2))
        return

    if args.action == "search":
        if not args.query:
            raise SystemExit("search action requires --query")
        if not args.resource_id and not args.name:
            raise SystemExit("search action requires --resource-id or --name")
        if not args.resource_id and args.name and not args.project:
            raise SystemExit("when using --name, --project (or env DATABASE_VIKING_PROJECT) is required")

        target_rid, _ = _resolve_authorized_target(
            client=client,
            resource_id=args.resource_id,
            name=args.name,
            project=args.project,
            allowed_ids=allowed_ids,
            allowed_set=allowed_set,
            max_workers=args.max_workers,
        )
        resp = client.search_knowledge(
            query=args.query,
            resource_id=target_rid,
            limit=args.limit,
        )
        _assert_response_collection_allowed(resp, allowed_set)
        print(json.dumps(resp, ensure_ascii=False, indent=2))
        return

    # auto
    if not args.query:
        raise SystemExit("auto action requires --query")

    if not allowed_ids:
        raise SystemExit(
            f"auto action requires allowed collection ids: set env {ALLOWED_COLLECTION_IDS_ENV} "
            "or pass --allowed-collection-ids"
        )

    collections = [{"resource_id": rid} for rid in allowed_ids]

    searched = _run_multi_search(
        client,
        collections=collections,
        query=args.query,
        limit=min(args.limit, 5),
        top_k=args.top_k,
        max_workers=args.max_workers,
    )

    output = {
        "mode": "multi",
        "query": args.query,
        "collections": searched,
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()