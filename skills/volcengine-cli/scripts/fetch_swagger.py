#!/usr/bin/env python3
"""
Fetch Volcengine API Swagger and convert to Markdown documentation.
Usage: python3 fetch_swagger.py --service ecs --action RunInstances [--version 2020-04-01]
"""

import argparse
import json
import sys
import urllib.request
import urllib.error

BASE_URL = "https://api.volcengine.com/api/common/explorer"


def fetch_json(url, allow_404=False):
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        if allow_404 and e.code == 404:
            return None
        print(f"Error fetching {url}: {e}", file=sys.stderr)
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f"Error fetching {url}: {e}", file=sys.stderr)
        sys.exit(1)


def get_all_versions(service_code):
    """Return all versions for a service, IsDefault=1 first."""
    url = f"{BASE_URL}/versions?ServiceCode={service_code}"
    data = fetch_json(url)
    assert data is not None
    versions = data.get("Result", {}).get("Versions", [])
    if not versions:
        print(f"No version found for service: {service_code}", file=sys.stderr)
        sys.exit(1)
    versions.sort(key=lambda v: 0 if v.get("IsDefault") == 1 else 1)
    return [v["Version"] for v in versions]


def get_default_version(service_code):
    return get_all_versions(service_code)[0]


def get_swagger(service_code, version, action_name, all_versions=None):
    """Fetch swagger for an action. If not found in given version, try all other versions."""
    def _try(ver):
        url = (
            f"{BASE_URL}/api-swagger"
            f"?ServiceCode={service_code}"
            f"&Version={ver}"
            f"&APIVersion={ver}"
            f"&ActionName={action_name}"
        )
        data = fetch_json(url, allow_404=True)
        if data is None:
            return None, None
        api = data.get("Result", {}).get("Api")
        return api, ver

    api, matched_ver = _try(version)
    if api:
        return api, matched_ver

    # Fallback: try remaining versions
    if all_versions is None:
        all_versions = get_all_versions(service_code)
    for ver in all_versions:
        if ver == version:
            continue
        api, matched_ver = _try(ver)
        if api:
            print(f"Note: action '{action_name}' not found in v{version}, using v{matched_ver}", file=sys.stderr)
            return api, matched_ver

    print(f"No swagger found for {service_code}.{action_name} in any version: {all_versions}", file=sys.stderr)
    sys.exit(1)


def resolve_ref(ref_str, schemas):
    """Resolve a $ref like '#/components/schemas/Foo' to its schema dict."""
    if ref_str.startswith("#/components/schemas/"):
        name = ref_str[len("#/components/schemas/"):]
        return name, schemas.get(name, {})
    return ref_str, {}


def get_type_str(schema, schemas):
    """Get a human-readable type string from a schema object."""
    if "$ref" in schema:
        name, _ = resolve_ref(schema["$ref"], schemas)
        return f"object({name})"
    t = schema.get("type", "string")
    if t == "array":
        items = schema.get("items", {})
        if "$ref" in items:
            name, _ = resolve_ref(items["$ref"], schemas)
            return f"array[object({name})]"
        return f"array[{items.get('type', 'string')}]"
    if t == "integer":
        fmt = schema.get("format", "")
        return "integer" if not fmt else f"integer({fmt})"
    if t == "number":
        return "number"
    return t


def escape_md(text):
    """Escape pipe characters and newlines for markdown table cells."""
    if not text:
        return ""
    text = str(text)
    # Collapse multi-line descriptions to single line, keep it readable
    text = text.replace("\n", " ").replace("|", "&#124;")
    # Trim markdown tip/note blocks
    import re
    text = re.sub(r":::.*?:::", "", text, flags=re.DOTALL).strip()
    # Limit length
    if len(text) > 200:
        text = text[:197] + "..."
    return text


def format_example(example):
    if example is None:
        return ""
    if isinstance(example, list):
        return ", ".join(str(e) for e in example[:2])
    return str(example)


def build_params_table(params_list):
    """Build a markdown table from a list of param dicts."""
    lines = [
        "| 参数名 | 类型 | 必填 | 说明 | 示例值 |",
        "|--------|------|:----:|------|--------|",
    ]
    for p in params_list:
        required = "✓" if p.get("required") else ""
        lines.append(
            f"| `{p['name']}` | {p['type']} | {required} | {escape_md(p.get('description', ''))} | {escape_md(format_example(p.get('example', '')))} |"
        )
    return "\n".join(lines)


def parse_get_params(parameters, schemas):
    """Parse GET query parameters, separating flat and nested ($ref) params."""
    flat = []
    nested = []  # list of (param_name, is_array, schema_name, schema_dict)

    for p in parameters:
        schema = p.get("schema", {})
        name = p.get("name", "")
        required = p.get("required", False)
        description = p.get("description", "")
        example = p.get("example")

        if "$ref" in schema:
            ref_name, ref_schema = resolve_ref(schema["$ref"], schemas)
            nested.append((name, False, ref_name, ref_schema, required, description))
        elif schema.get("type") == "array" and "$ref" in schema.get("items", {}):
            ref_name, ref_schema = resolve_ref(schema["items"]["$ref"], schemas)
            nested.append((name, True, ref_name, ref_schema, required, description))
        else:
            flat.append({
                "name": name,
                "type": get_type_str(schema, schemas),
                "required": required,
                "description": description,
                "example": example or schema.get("example"),
            })

    return flat, nested


def parse_nested_schema(schema_name, schema_dict, parent_prefix, is_array, schemas, visited=None):
    """Recursively parse a schema into a flat list of param dicts with full paths."""
    if visited is None:
        visited = set()
    if schema_name in visited:
        return []
    visited = visited | {schema_name}

    params = []
    properties = schema_dict.get("properties", {})
    sort_order = schema_dict.get("x-sort-params", [])

    # Use sort order if provided, otherwise alphabetical
    sorted_keys = sort_order if sort_order else sorted(properties.keys())
    # Make sure all keys are included (sort_order might be incomplete)
    sorted_keys = sorted_keys + [k for k in properties if k not in sorted_keys]

    for prop_name in sorted_keys:
        if prop_name not in properties:
            continue
        prop = properties[prop_name]
        full_name = f"{parent_prefix}.N.{prop_name}" if is_array else f"{parent_prefix}.{prop_name}"

        if "$ref" in prop:
            sub_name, sub_schema = resolve_ref(prop["$ref"], schemas)
            params.append({
                "name": full_name,
                "type": f"object",
                "required": False,
                "description": prop.get("description", ""),
                "example": prop.get("example"),
            })
            params.extend(parse_nested_schema(sub_name, sub_schema, full_name, False, schemas, visited))
        elif prop.get("type") == "array" and "$ref" in prop.get("items", {}):
            sub_name, sub_schema = resolve_ref(prop["items"]["$ref"], schemas)
            params.append({
                "name": full_name,
                "type": "array[object]",
                "required": False,
                "description": prop.get("description", ""),
                "example": prop.get("example"),
            })
            params.extend(parse_nested_schema(sub_name, sub_schema, full_name, True, schemas, visited))
        else:
            params.append({
                "name": full_name,
                "type": get_type_str(prop, schemas),
                "required": False,
                "description": prop.get("description", ""),
                "example": prop.get("example"),
            })

    return params


def parse_post_body(request_body, schemas):
    """Parse a POST requestBody schema into flat + nested params."""
    content = request_body.get("content", {})
    schema = content.get("application/json", {}).get("schema", {})

    # Handle top-level $ref
    if "$ref" in schema:
        _, schema = resolve_ref(schema["$ref"], schemas)

    flat = []
    nested_sections = []
    properties = schema.get("properties", {})
    required_list = schema.get("required", [])
    sort_order = schema.get("x-sort-params", [])
    sorted_keys = sort_order + [k for k in properties if k not in sort_order]

    for key in sorted_keys:
        if key not in properties:
            continue
        prop = properties[key]
        required = key in required_list
        description = prop.get("description", "")
        example = prop.get("example")

        if "$ref" in prop:
            ref_name, ref_schema = resolve_ref(prop["$ref"], schemas)
            flat.append({
                "name": key,
                "type": "object",
                "required": required,
                "description": description,
                "example": example,
            })
            nested_sections.append((key, False, ref_name, ref_schema))
        elif prop.get("type") == "array" and "$ref" in prop.get("items", {}):
            ref_name, ref_schema = resolve_ref(prop["items"]["$ref"], schemas)
            flat.append({
                "name": key,
                "type": "array[object]",
                "required": required,
                "description": description,
                "example": example,
            })
            nested_sections.append((key, True, ref_name, ref_schema))
        else:
            flat.append({
                "name": key,
                "type": get_type_str(prop, schemas),
                "required": required,
                "description": description,
                "example": example or prop.get("example"),
            })

    return flat, nested_sections


def swagger_to_markdown(service_code, action_name, version, api_swagger):
    schemas = api_swagger.get("components", {}).get("schemas", {})
    paths = api_swagger.get("paths", {})

    # Find the operation
    method = "GET"
    operation = {}
    for _, methods in paths.items():
        for m, op in methods.items():
            method = m.upper()
            operation = op
            break
        break

    # API description (from operation summary or first param description)
    summary = operation.get("summary", operation.get("description", ""))

    lines = []
    lines.append(f"# `ve {service_code} {action_name}`")
    if summary:
        lines.append(f"\n{summary.strip()}")
    lines.append(f"\n**服务**: `{service_code}` | **版本**: `{version}` | **方法**: `{method}`")
    lines.append(f"\n**CLI 格式**: `ve {service_code} {action_name} [参数...]`")
    lines.append("")

    if method == "GET":
        parameters = operation.get("parameters", [])
        flat_params, nested_list = parse_get_params(parameters, schemas)

        lines.append("## 请求参数\n")
        if flat_params:
            lines.append(build_params_table(flat_params))
        else:
            lines.append("_无独立参数_")

        for (param_name, is_array, schema_name, schema_dict, _, description) in nested_list:
            type_label = "array[object]" if is_array else "object"
            lines.append(f"\n### 嵌套参数：`{param_name}` ({type_label})\n")
            if description and description != param_name:
                lines.append(f"{description}\n")
            nested_params = parse_nested_schema(
                schema_name, schema_dict, param_name, is_array, schemas
            )
            if nested_params:
                lines.append(build_params_table(nested_params))

    else:  # POST
        request_body = operation.get("requestBody", {})
        if request_body:
            flat_params, nested_sections = parse_post_body(request_body, schemas)
            lines.append("## 请求参数 (Request Body JSON)\n")
            if flat_params:
                lines.append(build_params_table(flat_params))
            for (key, is_array, ref_name, ref_schema) in nested_sections:
                type_label = "array[object]" if is_array else "object"
                lines.append(f"\n### 嵌套参数：`{key}` ({type_label})\n")
                nested_params = parse_nested_schema(
                    ref_name, ref_schema, key, is_array, schemas
                )
                if nested_params:
                    lines.append(build_params_table(nested_params))
        else:
            params = operation.get("parameters", [])
            flat_params, nested_list = parse_get_params(params, schemas)
            lines.append("## 请求参数\n")
            if flat_params:
                lines.append(build_params_table(flat_params))
            for (param_name, is_array, schema_name, schema_dict, _req, _desc) in nested_list:
                type_label = "array[object]" if is_array else "object"
                lines.append(f"\n### 嵌套参数：`{param_name}` ({type_label})\n")
                nested_params = parse_nested_schema(
                    schema_name, schema_dict, param_name, is_array, schemas
                )
                if nested_params:
                    lines.append(build_params_table(nested_params))

    lines.append("\n---")
    lines.append(f"_生成自 Volcengine OpenAPI Explorer: {service_code} {action_name} v{version}_")
    return "\n".join(lines)


def list_apis(service_code, version):
    """List all available APIs for a service/version."""
    url = (
        f"{BASE_URL}/apis"
        f"?ServiceCode={service_code}"
        f"&Version={version}"
        f"&APIVersion={version}"
    )
    data = fetch_json(url)
    assert data is not None
    groups = data.get("Result", {}).get("Groups", [])
    lines = [f"# {service_code} v{version} API 列表\n"]
    for group in groups:
        group_name = group.get("Name", "")
        apis = group.get("Apis", [])
        if apis:
            lines.append(f"## {group_name}\n")
            for api in apis:
                action = api.get("Action", "")
                name_cn = api.get("NameCn", "")
                desc = api.get("Description", "")
                lines.append(f"- **{action}** - {name_cn}: {desc[:80]}")
            lines.append("")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Fetch Volcengine API Swagger and output as Markdown"
    )
    parser.add_argument("--service", "-s", required=True, help="Service code, e.g. ecs")
    parser.add_argument("--action", "-a", help="API action name, e.g. RunInstances")
    parser.add_argument("--version", "-v", help="API version, e.g. 2020-04-01 (auto-detected if omitted)")
    parser.add_argument("--list", "-l", action="store_true", help="List all APIs for the service")
    args = parser.parse_args()

    service_code = args.service
    all_versions = get_all_versions(service_code)
    version = args.version or all_versions[0]

    if args.list or not args.action:
        print(list_apis(service_code, version))
        return

    api_swagger, matched_version = get_swagger(service_code, version, args.action, all_versions)
    md = swagger_to_markdown(service_code, args.action, matched_version, api_swagger)
    print(md)


if __name__ == "__main__":
    main()
