# Copyright (c) 2026 ByteDance Ltd. and/or its affiliates
# SPDX-License-Identifier: MIT
import argparse
import json
import os
import sys
from typing import Any, Dict, Optional
from urllib.parse import urlparse


def print_result(data: Any) -> None:
    print(json.dumps({"status": "success", "data": data}, indent=2, ensure_ascii=False, default=str))


def print_error(msg: str, details: Optional[str] = None) -> None:
    err: Dict[str, Any] = {"error": msg}
    if details:
        err["details"] = details
    print(json.dumps(err, ensure_ascii=False))
    sys.exit(1)


def parse_json(raw: str, name: str) -> Any:
    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        print_error("Invalid JSON", f"Invalid JSON in {name}: {str(e)}")


def parse_endpoint(endpoint: str) -> Dict[str, Any]:
    u = urlparse(endpoint)
    if not u.scheme or not u.hostname:
        print_error("Invalid Endpoint", "Endpoint must include scheme and host, e.g. https://domain:9200")
    scheme = u.scheme.lower()
    if scheme not in ("http", "https"):
        print_error("Invalid Endpoint", "Endpoint scheme must be http or https")
    port = u.port or (443 if scheme == "https" else 80)
    return {"host": u.hostname, "port": port, "scheme": scheme}


def build_client(args):
    try:
        from opensearchpy import OpenSearch
    except Exception as e:
        print_error(
            "Missing Dependency",
            f"Failed to import opensearch-py: {str(e)}. Instruction: install dependencies with '{args.base_python} -m pip install -r requirements.txt'.",
        )

    endpoint = args.endpoint or os.environ.get("ESCLOUD_ENDPOINT", "")
    if not endpoint:
        print_error("Missing Endpoint", "Provide --endpoint or set ESCLOUD_ENDPOINT.")

    host = parse_endpoint(endpoint)

    username = args.username or os.environ.get("ESCLOUD_USERNAME", "")
    password = args.password or os.environ.get("ESCLOUD_PASSWORD", "")
    api_key = args.api_key or os.environ.get("ESCLOUD_API_KEY", "")
    bearer = args.bearer_token or os.environ.get("ESCLOUD_BEARER_TOKEN", "")

    if sum(1 for x in [(username or password), api_key, bearer] if x) > 1:
        print_error("Invalid Auth", "Specify only one auth method: basic OR api-key OR bearer-token.")
    if password and not username:
        print_error("Invalid Auth", "When using basic auth, --username is required if --password is set.")

    headers: Dict[str, str] = {}
    http_auth = None
    if username:
        http_auth = (username, password)
    if api_key:
        headers["Authorization"] = f"ApiKey {api_key}"
    if bearer:
        headers["Authorization"] = f"Bearer {bearer}"

    insecure_env = os.environ.get("ESCLOUD_INSECURE", "")
    insecure_default = insecure_env.lower() in ("true", "1", "yes", "y")
    insecure = args.insecure or insecure_default
    ca_certs = args.ca_certs or os.environ.get("ESCLOUD_CA_CERTS", "")

    try:
        return OpenSearch(
            hosts=[host],
            http_auth=http_auth,
            headers=headers or None,
            verify_certs=not insecure,
            ca_certs=ca_certs or None,
            timeout=args.timeout,
            http_compress=args.http_compress,
        )
    except Exception as e:
        print_error("Failed to Create Client", f"{str(e)}. Instruction: Verify endpoint/auth/TLS options.")


def preflight_info(client) -> Dict[str, Any]:
    try:
        info = client.info()
    except Exception as e:
        print_error(
            "Connectivity Check Failed",
            f"{str(e)}\n\nInstruction: Verify endpoint reachability and IP allowlist; then verify credentials.",
        )
    if not isinstance(info, dict):
        return {"raw": str(info)}
    return info


def detect_engine(info: Dict[str, Any]) -> Dict[str, str]:
    version = (info.get("version") or {}) if isinstance(info, dict) else {}
    number = str(version.get("number") or "")
    distribution = str(version.get("distribution") or "")
    engine = "opensearch" if distribution.lower() == "opensearch" else "elasticsearch"
    return {"engine": engine, "version": number or distribution or "unknown"}


def maybe_apply_es8_compat_headers(client, server: Dict[str, str]) -> None:
    # Limited support improvement: if it's Elasticsearch 8.x, add compatibility headers.
    # Keep OpenSearch unaffected.
    if server.get("engine") != "elasticsearch":
        return
    ver = server.get("version", "")
    if not ver.startswith("8."):
        return
    headers = getattr(client.transport, "headers", None)
    if headers is None:
        return
    headers.setdefault("Accept", "application/vnd.elasticsearch+json; compatible-with=7")
    headers.setdefault("Content-Type", "application/vnd.elasticsearch+json; compatible-with=7")


def cmd_info(client, args):
    info = preflight_info(client)
    server = detect_engine(info)
    print_result({"server": server, "info": info})


def cmd_index_create(client, args):
    info = preflight_info(client)
    server = detect_engine(info)
    maybe_apply_es8_compat_headers(client, server)

    body: Dict[str, Any] = {}
    if args.settings:
        body["settings"] = parse_json(args.settings, "--settings")
    if args.mappings:
        body["mappings"] = parse_json(args.mappings, "--mappings")
    try:
        res = client.indices.create(index=args.index, body=body or None)
    except Exception as e:
        print_error("Index Create Failed", str(e))
    print_result({"server": server, "result": res})


def cmd_index_delete(client, args):
    info = preflight_info(client)
    server = detect_engine(info)
    maybe_apply_es8_compat_headers(client, server)
    if not getattr(args, "confirm", False):
        print_error(
            "Confirmation Required",
            "Refusing to delete without --confirm. Ask the user to explicitly confirm, then rerun with: data.py --endpoint <endpoint> index_delete --index <name> --confirm",
        )
    try:
        res = client.indices.delete(index=args.index)
    except Exception as e:
        print_error("Index Delete Failed", str(e))
    print_result({"server": server, "result": res})


def cmd_index_exists(client, args):
    info = preflight_info(client)
    server = detect_engine(info)
    maybe_apply_es8_compat_headers(client, server)
    try:
        exists = client.indices.exists(index=args.index)
    except Exception as e:
        print_error("Index Exists Failed", str(e))
    print_result({"server": server, "index": args.index, "exists": bool(exists)})


def cmd_index_list(client, args):
    info = preflight_info(client)
    server = detect_engine(info)
    maybe_apply_es8_compat_headers(client, server)
    try:
        indices = client.cat.indices(format="json")
        print_result({"server": server, "indices": indices})
        return
    except Exception:
        pass
    try:
        aliases = client.indices.get_alias(index="*")
        print_result({"server": server, "indices": sorted(list(aliases.keys()))})
    except Exception as e:
        print_error("Index List Failed", str(e))


def cmd_index_get(client, args):
    info = preflight_info(client)
    server = detect_engine(info)
    maybe_apply_es8_compat_headers(client, server)
    try:
        settings = client.indices.get_settings(index=args.index)
        mappings = client.indices.get_mapping(index=args.index)
    except Exception as e:
        print_error("Index Get Failed", str(e))
    print_result({"server": server, "settings": settings, "mappings": mappings})


def cmd_doc_index(client, args):
    info = preflight_info(client)
    server = detect_engine(info)
    maybe_apply_es8_compat_headers(client, server)

    doc = parse_json(args.doc, "--doc")
    if not isinstance(doc, dict):
        print_error("Invalid --doc", "--doc must be a JSON object, e.g. '{\"field\":\"value\"}'")
    kwargs: Dict[str, Any] = {"index": args.index, "body": doc}
    if args.id:
        kwargs["id"] = args.id
    if args.refresh is not None:
        kwargs["refresh"] = args.refresh
    try:
        res = client.index(**kwargs)
    except Exception as e:
        print_error("Doc Index Failed", str(e))
    print_result({"server": server, "result": res})


def cmd_doc_get(client, args):
    info = preflight_info(client)
    server = detect_engine(info)
    maybe_apply_es8_compat_headers(client, server)
    try:
        res = client.get(index=args.index, id=args.id)
    except Exception as e:
        print_error("Doc Get Failed", str(e))
    print_result({"server": server, "result": res})


def cmd_doc_delete(client, args):
    info = preflight_info(client)
    server = detect_engine(info)
    maybe_apply_es8_compat_headers(client, server)
    if not getattr(args, "confirm", False):
        print_error(
            "Confirmation Required",
            "Refusing to delete without --confirm. Ask the user to explicitly confirm, then rerun with: data.py --endpoint <endpoint> doc_delete --index <name> --id <id> --confirm",
        )
    kwargs: Dict[str, Any] = {"index": args.index, "id": args.id}
    if args.refresh is not None:
        kwargs["refresh"] = args.refresh
    try:
        res = client.delete(**kwargs)
    except Exception as e:
        print_error("Doc Delete Failed", str(e))
    print_result({"server": server, "result": res})


def cmd_search(client, args):
    info = preflight_info(client)
    server = detect_engine(info)
    maybe_apply_es8_compat_headers(client, server)

    query = parse_json(args.query, "--query")
    if not isinstance(query, dict):
        print_error("Invalid --query", "--query must be a JSON object")
    try:
        res = client.search(index=args.index, body=query, from_=args.from_, size=args.size)
    except TypeError:
        # Some clients don't accept from_ kw; use from in body.
        query.setdefault("from", args.from_)
        query.setdefault("size", args.size)
        try:
            res = client.search(index=args.index, body=query)
        except Exception as e:
            print_error("Search Failed", str(e))
    except Exception as e:
        print_error("Search Failed", str(e))
    print_result({"server": server, "result": res})


def read_text_file(path: str) -> str:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        print_error("Failed to Read File", f"{str(e)}. Instruction: Verify the file path and encoding.")


def cmd_bulk(client, args):
    info = preflight_info(client)
    server = detect_engine(info)
    maybe_apply_es8_compat_headers(client, server)

    if bool(args.file) == bool(args.body):
        print_error("Invalid Bulk Input", "Specify exactly one of --file or --body.")
    ndjson = read_text_file(args.file) if args.file else args.body
    if not ndjson.endswith("\n"):
        ndjson += "\n"

    # Use the transport layer to send NDJSON as-is.
    try:
        res = client.transport.perform_request(
            "POST",
            "/_bulk",
            body=ndjson,
            headers={"Content-Type": "application/x-ndjson"},
        )
    except Exception as e:
        print_error(
            "Bulk Failed",
            f"{str(e)}\n\nInstruction: Ensure the request body is valid NDJSON and the cluster allows bulk requests.",
        )
    print_result({"server": server, "result": res})


def add_common_connection_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--endpoint", default="", help="Endpoint URL, e.g. https://domain:9200 (or set ESCLOUD_ENDPOINT)")
    parser.add_argument("--username", default="", help="Basic auth username (or set ESCLOUD_USERNAME)")
    parser.add_argument("--password", default="", help="Basic auth password (or set ESCLOUD_PASSWORD)")
    parser.add_argument("--api-key", default="", help="API key for Authorization header (or set ESCLOUD_API_KEY)")
    parser.add_argument("--bearer-token", default="", help="Bearer token for Authorization header (or set ESCLOUD_BEARER_TOKEN)")
    parser.add_argument("--ca-certs", default="", help="Path to CA bundle (or set ESCLOUD_CA_CERTS)")
    parser.add_argument("--insecure", action="store_true", help="Disable TLS cert verification (or set ESCLOUD_INSECURE=true)")
    parser.add_argument("--timeout", type=int, default=30, help="Request timeout seconds (default: 30)")
    parser.add_argument("--http-compress", type=str_to_bool, default=True, help="Enable HTTP compression (default: true)")


def str_to_bool(v: str) -> bool:
    if v.lower() in ("true", "1", "yes", "y"):
        return True
    if v.lower() in ("false", "0", "no", "n"):
        return False
    raise argparse.ArgumentTypeError(f"Boolean value expected, got '{v}'")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="ESCloud data plane CLI (opensearch-py)")
    parser.set_defaults(base_python=sys.executable)
    add_common_connection_args(parser)
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("info", help="Connectivity check and server info")
    p.set_defaults(func=cmd_info)

    p = sub.add_parser("index_create", help="Create an index")
    p.add_argument("--index", required=True)
    p.add_argument("--settings", default="", help="JSON object for settings")
    p.add_argument("--mappings", default="", help="JSON object for mappings")
    p.set_defaults(func=cmd_index_create)

    p = sub.add_parser("index_delete", help="Delete an index")
    p.add_argument("--index", required=True)
    p.add_argument("--confirm", action="store_true", help="Required safety flag for deletion")
    p.set_defaults(func=cmd_index_delete)

    p = sub.add_parser("index_exists", help="Check index existence")
    p.add_argument("--index", required=True)
    p.set_defaults(func=cmd_index_exists)

    p = sub.add_parser("index_list", help="List indices")
    p.set_defaults(func=cmd_index_list)

    p = sub.add_parser("index_get", help="Get settings/mappings for an index")
    p.add_argument("--index", required=True)
    p.set_defaults(func=cmd_index_get)

    p = sub.add_parser("doc_index", help="Index (create/update) a document")
    p.add_argument("--index", required=True)
    p.add_argument("--doc", required=True, help="JSON object document")
    p.add_argument("--id", default="", help="Optional document ID")
    p.add_argument("--refresh", type=str_to_bool, default=None, help="Optional refresh true/false")
    p.set_defaults(func=cmd_doc_index)

    p = sub.add_parser("doc_get", help="Get a document by ID")
    p.add_argument("--index", required=True)
    p.add_argument("--id", required=True)
    p.set_defaults(func=cmd_doc_get)

    p = sub.add_parser("doc_delete", help="Delete a document by ID")
    p.add_argument("--index", required=True)
    p.add_argument("--id", required=True)
    p.add_argument("--confirm", action="store_true", help="Required safety flag for deletion")
    p.add_argument("--refresh", type=str_to_bool, default=None, help="Optional refresh true/false")
    p.set_defaults(func=cmd_doc_delete)

    p = sub.add_parser("search", help="Search documents")
    p.add_argument("--index", required=True)
    p.add_argument("--query", required=True, help="JSON query body")
    p.add_argument("--from", dest="from_", type=int, default=0, help="Offset (default: 0)")
    p.add_argument("--size", type=int, default=10, help="Size (default: 10)")
    p.set_defaults(func=cmd_search)

    p = sub.add_parser("bulk", help="Bulk ingest (NDJSON)")
    p.add_argument("--file", default="", help="Path to NDJSON file")
    p.add_argument("--body", default="", help="Raw NDJSON string")
    p.set_defaults(func=cmd_bulk)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    client = build_client(args)
    args.func(client, args)


if __name__ == "__main__":
    main()
