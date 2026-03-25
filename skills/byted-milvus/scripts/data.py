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
import argparse
import json
import os
import sys

from typing import Optional, Tuple

from pymilvus import MilvusClient, model
from pymilvus import DataType
from pymilvus.milvus_client.index import IndexParams
from pymilvus.orm.schema import CollectionSchema, FieldSchema


def print_result(data):
    """Print a successful JSON result."""
    print(json.dumps({"status": "success", "data": data}, indent=2, default=str))


def print_error(msg, details=None):
    """Print a JSON error and exit."""
    err = {"error": msg}
    if details:
        err["details"] = details
    print(json.dumps(err))
    sys.exit(1)

def env_int(name: str):
    """Parse an integer env var; return None if unset."""
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return None
    try:
        return int(raw)
    except ValueError:
        print_error(f"Invalid environment variable: {name}", f"Expected an integer, got: {raw!r}")

def load_json_from_arg(schema_json: Optional[str], schema_file: Optional[str]) -> Optional[dict]:
    if schema_json and schema_file:
        print_error("Conflicting arguments", "Provide only one of --schema-json or --schema-file.")
    if schema_file:
        try:
            with open(schema_file, "r", encoding="utf-8") as f:
                schema_json = f.read()
        except Exception as e:
            print_error("Failed to read schema file", f"{schema_file}: {e}")
    if not schema_json:
        return None
    try:
        obj = json.loads(schema_json)
    except json.JSONDecodeError as e:
        print_error("Invalid JSON in schema", f"{str(e)}. Instruction: Provide valid JSON via --schema-json or --schema-file.")
    if not isinstance(obj, dict):
        print_error("Invalid schema JSON", "Schema must be a JSON object.")
    return obj


def parse_field_type(type_str: str):
    t = (type_str or "").upper()
    # Allow common aliases to keep schema JSON ergonomic.
    if t in ("INT", "INTEGER"):
        t = "INT64"
    if t in ("STRING",):
        t = "VARCHAR"
    if t in ("VECTOR",):
        t = "FLOAT_VECTOR"
    if t == "INT64":
        return DataType.INT64
    if t == "VARCHAR":
        return DataType.VARCHAR
    if t == "FLOAT_VECTOR":
        return DataType.FLOAT_VECTOR
    print_error("Unsupported field type in schema", f"type={type_str!r}. Supported: INT64, VARCHAR, FLOAT_VECTOR (aliases: INT/INTEGER, STRING, VECTOR).")


def schema_to_pymilvus(schema_obj: dict) -> Tuple[CollectionSchema, Optional[IndexParams]]:
    enable_dynamic_field = schema_obj.get("enable_dynamic_field", False)
    if not isinstance(enable_dynamic_field, bool):
        print_error("Invalid schema", "enable_dynamic_field must be a boolean.")

    # Optional ergonomic defaults.
    default_dim = schema_obj.get("dimension", None)
    if default_dim is not None and (not isinstance(default_dim, int) or default_dim <= 0):
        print_error("Invalid schema", "dimension must be an integer > 0 if provided.")
    default_varchar_max_length = schema_obj.get("varchar_max_length", None)
    if default_varchar_max_length is not None and (not isinstance(default_varchar_max_length, int) or default_varchar_max_length <= 0):
        print_error("Invalid schema", "varchar_max_length must be an integer > 0 if provided.")

    fields_obj = schema_obj.get("fields")
    if not isinstance(fields_obj, list) or not fields_obj:
        print_error("Invalid schema", "fields must be a non-empty array.")

    # Normalize schema to support an ergonomic top-level primary_key block.
    # Backward compatible: also supports per-field `primary_key` boolean.
    fields_norm: list[dict] = []
    for f in fields_obj:
        if not isinstance(f, dict):
            print_error("Invalid schema", "Each item in fields must be an object.")
        fields_norm.append(dict(f))

    pk_obj = schema_obj.get("primary_key", None)
    if pk_obj is not None:
        if not isinstance(pk_obj, dict):
            print_error("Invalid schema", "primary_key must be an object if provided.")
        pk_name = pk_obj.get("name")
        pk_type = pk_obj.get("type")
        if not isinstance(pk_name, str) or not pk_name:
            print_error("Invalid schema", "primary_key.name must be a non-empty string.")
        if not isinstance(pk_type, str) or not pk_type:
            print_error("Invalid schema", "primary_key.type must be a non-empty string.")
        pk_entry = dict(pk_obj)
        pk_entry["name"] = pk_name
        pk_entry["type"] = pk_type
        pk_entry["primary_key"] = True

        found = False
        for i, f in enumerate(fields_norm):
            if f.get("name") == pk_name:
                merged = dict(f)
                merged.update(pk_entry)  # primary_key block overrides field entry
                fields_norm[i] = merged
                found = True
                break
        if not found:
            # Put PK first for readability; not required by Milvus, but helps humans.
            fields_norm.insert(0, pk_entry)

        # Ensure no other field tries to be a primary key.
        for f in fields_norm:
            if f.get("name") != pk_name and (f.get("primary_key") or f.get("is_primary")):
                print_error(
                    "Invalid schema",
                    "primary_key is specified at top-level, but another field also declares primary key. "
                    "Instruction: use only one primary key definition.",
                )

    pk_fields = []
    vector_fields = []
    fields: list[FieldSchema] = []
    seen_names = set()
    for f in fields_norm:
        name = f.get("name")
        if not isinstance(name, str) or not name:
            print_error("Invalid schema", "Field name must be a non-empty string.")
        if name in seen_names:
            print_error("Invalid schema", f"Duplicate field name: {name!r}.")
        seen_names.add(name)
        dtype = parse_field_type(f.get("type"))

        is_pk = bool(f.get("primary_key", f.get("is_primary", False)))
        auto_id = bool(f.get("auto_id", False))
        nullable = bool(f.get("nullable", False))
        field_desc = f.get("description", "")
        if field_desc is None:
            field_desc = ""
        if not isinstance(field_desc, str):
            print_error("Invalid schema", f"Field {name!r} description must be a string if provided.")

        kwargs = {"is_primary": is_pk, "nullable": nullable}
        if is_pk:
            pk_fields.append(f)
            if auto_id:
                if dtype != DataType.INT64:
                    print_error("Invalid schema", "auto_id is only supported for INT64 primary keys.")
                kwargs["auto_id"] = True

        if dtype == DataType.VARCHAR:
            max_length = f.get("max_length", default_varchar_max_length)
            if not isinstance(max_length, int) or max_length <= 0:
                print_error("Invalid schema", f"Field {name!r} VARCHAR requires integer max_length > 0.")
            kwargs["max_length"] = max_length
        elif dtype == DataType.FLOAT_VECTOR:
            dim = f.get("dim", default_dim)
            if not isinstance(dim, int) or dim <= 0:
                print_error("Invalid schema", f"Field {name!r} FLOAT_VECTOR requires integer dim > 0.")
            kwargs["dim"] = dim
            vector_fields.append(name)

        fields.append(FieldSchema(name=name, dtype=dtype, description=field_desc, **kwargs))

    if len(pk_fields) != 1:
        print_error("Invalid schema", f"Schema must contain exactly one primary key field. Found {len(pk_fields)}.")
    if not vector_fields:
        print_error("Invalid schema", "Schema must contain at least one vector field (FLOAT_VECTOR).")

    # CollectionSchema accepts auto_id; set it true if the pk field uses auto_id.
    schema_auto_id = bool(pk_fields[0].get("auto_id", False))
    description = schema_obj.get("description", "")
    if not isinstance(description, str):
        print_error("Invalid schema", "description must be a string if provided.")

    schema = CollectionSchema(
        fields=fields,
        description=description,
        enable_dynamic_field=enable_dynamic_field,
        auto_id=schema_auto_id,
    )

    index_obj = schema_obj.get("index")
    if index_obj is None:
        # Default behavior: create a single AUTOINDEX on the first vector field.
        index_params = IndexParams()
        index_params.add_index(vector_fields[0], index_type="AUTOINDEX", metric_type="COSINE")
        return schema, index_params

    if not isinstance(index_obj, dict):
        print_error("Invalid schema", "index must be an object if provided.")

    field_name = index_obj.get("field_name") or vector_fields[0]
    if field_name not in vector_fields:
        print_error("Invalid schema", f"index.field_name must refer to a vector field. Got {field_name!r}.")
    index_type = index_obj.get("index_type", "AUTOINDEX")
    metric_type = index_obj.get("metric_type", "COSINE")
    params = index_obj.get("params", {})
    if params is None:
        params = {}
    if not isinstance(params, dict):
        print_error("Invalid schema", "index.params must be an object if provided.")

    index_params = IndexParams()
    index_params.add_index(field_name, index_type=index_type, metric_type=metric_type, params=params)
    return schema, index_params


KNOWN_EMBEDDING_DIMS = {
    # OpenAI
    "text-embedding-3-small": 1536,
    "text-embedding-3-large": 3072,
    "text-embedding-ada-002": 1536,
    # Volcengine (Doubao) via OpenAI-compatible embeddings API
    "doubao-embedding-large-text-250515": 2048,
    "doubao-embedding-large-text-240915": 4096,
    "doubao-embedding-text-240715": 2560,
    "doubao-embedding-text-240515": 2048,
}


def infer_embedding_dim(model_name: str, override_dimensions: Optional[int]) -> int:
    """Infer the embedding dimension used by the provider/model.

    We do not call the embedding API to discover dimensions (that would be slow/costly).
    If the model is unknown, require the user to provide --embed-dimensions / MS_EMBEDDING_DIMENSIONS.
    """
    if override_dimensions is not None:
        return override_dimensions
    dim = KNOWN_EMBEDDING_DIMS.get(model_name)
    if dim is None:
        print_error(
            "Cannot infer embedding dimensions for the selected model",
            f"model={model_name!r}. Instruction: set --embed-dimensions <n> or MS_EMBEDDING_DIMENSIONS=<n>, "
            "or choose a known model with documented dims.",
        )
    return dim


def extract_vector_field(desc: dict, field_name: str) -> dict:
    """Find a field by name in describe_collection output."""
    fields = desc.get("fields") if isinstance(desc, dict) else None
    if not isinstance(fields, list):
        print_error("Unexpected describe_collection output", "Missing 'fields' array in response.")
    for f in fields:
        if isinstance(f, dict) and f.get("name") == field_name:
            return f
    print_error(
        "Vector field not found in collection schema",
        f"field={field_name!r}. Instruction: run 'describe_collection' and verify the vector field name.",
    )


def is_vector_type(data_type) -> bool:
    # PyMilvus returns data_type as int enum value (commonly) in describe_collection output.
    vector_type_names = {
        "BINARY_VECTOR",
        "FLOAT_VECTOR",
        "FLOAT16_VECTOR",
        "BFLOAT16_VECTOR",
        "SPARSE_FLOAT_VECTOR",
        "INT8_VECTOR",
    }
    try:
        # DataType(int_value).name
        from pymilvus import DataType
        return DataType(data_type).name in vector_type_names
    except Exception:
        # Best-effort fallback for unexpected formats.
        return False


def require_schema_match_for_embedding(client: MilvusClient, collection: str, vector_field: str, expected_dim: int):
    """Verify that the collection's vector field exists, is vector-typed, and matches expected_dim."""
    desc = client.describe_collection(collection_name=collection)
    f = extract_vector_field(desc, vector_field)
    if not is_vector_type(f.get("data_type")):
        print_error(
            "Selected field is not a vector field",
            f"collection={collection!r}, field={vector_field!r}, data_type={f.get('data_type')!r}. "
            "Instruction: choose a vector field (e.g., FLOAT_VECTOR) for embedding/search.",
        )
    dim = f.get("dim")
    if not isinstance(dim, int):
        print_error(
            "Unexpected schema for vector field",
            f"collection={collection!r}, field={vector_field!r}. Missing integer 'dim' in describe_collection output.",
        )
    if dim != expected_dim:
        print_error(
            "Embedding dimension does not match collection schema",
            f"collection={collection!r}, field={vector_field!r}, schema_dim={dim}, embedding_dim={expected_dim}. "
            "Instruction: pick a model/dim that matches the collection, or recreate the collection with --dimension matching the embedding output.",
        )


def list_vector_field_names(desc: dict) -> list[str]:
    fields = desc.get("fields") if isinstance(desc, dict) else None
    if not isinstance(fields, list):
        return []
    out = []
    for f in fields:
        if not isinstance(f, dict):
            continue
        if is_vector_type(f.get("data_type")):
            n = f.get("name")
            if isinstance(n, str) and n:
                out.append(n)
    return out


def require_vectors_or_auto_embedding(client: MilvusClient, collection: str, data: list, *, embed_model: str, embed_field: str, text_field: str):
    """Enforce auto-embedding-only behavior for inserts/upserts.

    This skill intentionally does not allow users/agents to pass vectors directly. It reduces the risk
    of agents fabricating placeholder vectors and provides deterministic behavior.
    """
    if not (embed_model and embed_field and text_field):
        print_error(
            "Auto-embedding required",
            "This CLI only supports text -> embedding workflows for insert/upsert.\n"
            "Instruction: provide raw text in a field (e.g. 'text') and pass auto-embedding flags:\n"
            "  --embed-provider <openai|volcengine> --embed-model <model> --text-field <text_field> --embed-field <vector_field>\n"
            "Do not provide vectors in --data.",
        )
    desc = client.describe_collection(collection_name=collection)
    vector_fields = list_vector_field_names(desc)
    if not vector_fields:
        # Collection should always have a vector field, but keep behavior defensive.
        return

    bad_rows = []
    missing_text_rows = []
    bad_text_type_rows = []
    for i, item in enumerate(data):
        if not isinstance(item, dict):
            bad_rows.append(i)
            continue
        if any(vf in item for vf in vector_fields):
            bad_rows.append(i)
        if text_field not in item:
            missing_text_rows.append(i)
        else:
            if not isinstance(item.get(text_field), str):
                bad_text_type_rows.append(i)

    if bad_rows:
        preview = ", ".join(map(str, bad_rows[:10]))
        print_error(
            "Direct vector input is not supported",
            "This CLI rejects any input rows that include vector field values.\n"
            f"collection={collection!r}\n"
            f"vector_fields={vector_fields}\n"
            f"offending_row_indexes=[{preview}{', ...' if len(bad_rows) > 10 else ''}]\n"
            "Instruction: remove vector fields from --data and provide only raw text + metadata; "
            "the CLI will compute embeddings and populate the vector field.",
        )

    if missing_text_rows:
        preview = ", ".join(map(str, missing_text_rows[:10]))
        print_error(
            "Missing text field for auto-embedding",
            f"--text-field is set to {text_field!r}, but some rows are missing that field.\n"
            f"missing_row_indexes=[{preview}{', ...' if len(missing_text_rows) > 10 else ''}]\n"
            "Instruction: include that text field in every row (or choose the correct --text-field).",
        )

    if bad_text_type_rows:
        preview = ", ".join(map(str, bad_text_type_rows[:10]))
        print_error(
            "Invalid text field type for auto-embedding",
            f"--text-field {text_field!r} must be a string.\n"
            f"bad_row_indexes=[{preview}{', ...' if len(bad_text_type_rows) > 10 else ''}]\n"
            "Instruction: ensure the text field values are strings (not objects/numbers).",
        )


def get_embedding_model(model_name, provider=None, base_url=None, dimensions=None):
    if not provider:
         print_error("Embedding provider not specified. Please ask the user to choose 'openai' or 'volcengine'. You can also set MS_EMBEDDING_PROVIDER in the environment.")

    if not model_name:
         print_error("Embedding model_name not specified. Please ask the user to choose a model (e.g. 'text-embedding-3-small' for openai, or an endpoint ID for volcengine). You can also set MS_EMBEDDING_MODEL in the environment.")

    if provider in ("openai", "volcengine"):
        from pymilvus.model.dense import OpenAIEmbeddingFunction

        api_key = os.environ.get("MS_EMBEDDING_API_KEY")

        if not api_key:
            print_error(f"Missing environment variable: MS_EMBEDDING_API_KEY is required for {provider} models. Please ask the user to provide it.")

        kwargs = {"model_name": model_name, "api_key": api_key}
        if dimensions is not None:
            kwargs["dimensions"] = dimensions
        if base_url:
            kwargs["base_url"] = base_url
        elif provider == "volcengine":
            kwargs["base_url"] = "https://ark.cn-beijing.volces.com/api/v3"

        return OpenAIEmbeddingFunction(**kwargs)
    else:
        print_error(f"Unsupported embedding provider '{provider}'. Please ask the user to choose from 'openai' or 'volcengine'.")


def embed_data(args, data):
    """Apply auto-embedding to data if embed flags are provided. Mutates data in place."""
    if args.embed_model and args.embed_field and args.text_field:
        embed_fn = get_embedding_model(args.embed_model, args.embed_provider, args.embed_base_url, args.embed_dimensions)
        texts = [item.get(args.text_field, "") for item in data]
        vectors = embed_fn.encode_documents(texts)
        for i, item in enumerate(data):
            item[args.embed_field] = vectors[i]


def parse_json_data(raw, name="--data"):
    """Parse a JSON string and validate it's a list."""
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        print_error(
            f"Invalid JSON in {name}",
            f"{str(e)}. Instruction: Ensure the JSON is a valid string. For example, "
            "'[{\"id\": 1, \"text\": \"hello\"}]' for insert (auto-embedding), or '[\"query text\"]' for search.",
        )
    if not isinstance(data, list):
        print_error(f"{name} must be a JSON array", "Instruction: Wrap your data in square brackets []. For example, [{\"field\": \"value\"}].")
    return data


def connect(args):
    """Create a MilvusClient from parsed args."""
    try:
        if args.username and args.password:
            return MilvusClient(uri=args.endpoint, user=args.username, password=args.password)
        elif args.username:
            return MilvusClient(uri=args.endpoint, token=args.username)
        else:
            return MilvusClient(uri=args.endpoint)
    except Exception as e:
        print_error("Failed to connect to Milvus", f"{str(e)}. Instruction: Verify that the Milvus endpoint is reachable and that credentials are correct. For serverless instances, Ensure Public Access is enabled in the Volcano Engine WebUI.")


# --- Command handlers ---

def cmd_create_collection(client, args):
    schema_obj = load_json_from_arg(args.schema_json, args.schema_file)
    if schema_obj is not None:
        schema, index_params = schema_to_pymilvus(schema_obj)
        client.create_collection(
            collection_name=args.collection,
            schema=schema,
            index_params=index_params,
        )
        print_result(
            {
                "message": f"Collection '{args.collection}' created",
                "collection": args.collection,
                "schema_mode": "custom",
                "enable_dynamic_field": schema_obj.get("enable_dynamic_field", False),
                "description": schema_obj.get("description", ""),
            }
        )
        return

    if args.dimension is None:
        print_error("Missing argument", "When not using --schema-json/--schema-file, --dimension is required.")

    kwargs = {}
    # Default new collections to schema discipline (dynamic fields disabled unless explicitly enabled).
    kwargs["enable_dynamic_field"] = bool(args.enable_dynamic_field)
    # Only meaningful when id_type is VARCHAR/string.
    if args.pk_max_length is not None:
        kwargs["max_length"] = args.pk_max_length

    client.create_collection(
        collection_name=args.collection,
        dimension=args.dimension,
        primary_field_name=args.primary_field_name,
        id_type=args.id_type,
        vector_field_name=args.vector_field_name,
        metric_type=args.metric_type,
        auto_id=args.auto_id,
        **kwargs,
    )

    # Return an explicit schema summary so callers can present/confirm it.
    print_result(
        {
            "message": f"Collection '{args.collection}' created",
            "collection": args.collection,
            "dimension": args.dimension,
            "primary_field_name": args.primary_field_name,
            "id_type": args.id_type,
            "auto_id": args.auto_id,
            "vector_field_name": args.vector_field_name,
            "metric_type": args.metric_type,
            "enable_dynamic_field": kwargs.get("enable_dynamic_field", False),
            "pk_max_length": kwargs.get("max_length"),
            "schema_mode": "fast",
        }
    )


def cmd_drop_collection(client, args):
    if not args.confirm:
        print_error(
            "Confirmation required",
            "Refusing to drop collection without explicit confirmation.\n"
            f"Target collection: {args.collection!r}\n"
            "Instruction: Run 'describe_collection' first and show the schema to the user, then ask them to confirm.\n"
            f"1) data.py describe_collection --collection {args.collection}\n"
            f"2) data.py drop_collection --collection {args.collection} --confirm {args.collection}",
        )
    if args.confirm != args.collection:
        print_error(
            "Confirmation mismatch",
            f"--confirm must exactly match the collection name. Expected {args.collection!r}, got {args.confirm!r}.",
        )
    client.drop_collection(collection_name=args.collection)
    print_result({"message": f"Collection '{args.collection}' dropped"})


def cmd_has_collection(client, args):
    exists = client.has_collection(collection_name=args.collection)
    print_result({"collection": args.collection, "exists": exists})


def cmd_list_collections(client, args):
    collections = client.list_collections()
    print_result({"collections": collections})


def cmd_describe_collection(client, args):
    desc = client.describe_collection(collection_name=args.collection)
    print_result(desc)


def cmd_read(client, args):
    res = client.query(collection_name=args.collection, filter=args.filter, limit=args.limit)
    print_result(res)


def cmd_insert(client, args):
    data = parse_json_data(args.data)
    require_vectors_or_auto_embedding(
        client,
        args.collection,
        data,
        embed_model=args.embed_model,
        embed_field=args.embed_field,
        text_field=args.text_field,
    )
    if args.verify_schema:
        expected_dim = infer_embedding_dim(args.embed_model, args.embed_dimensions)
        require_schema_match_for_embedding(client, args.collection, args.embed_field, expected_dim)
    embed_data(args, data)
    res = client.insert(collection_name=args.collection, data=data)
    print_result({"insert_result": str(res)})


def cmd_upsert(client, args):
    data = parse_json_data(args.data)
    require_vectors_or_auto_embedding(
        client,
        args.collection,
        data,
        embed_model=args.embed_model,
        embed_field=args.embed_field,
        text_field=args.text_field,
    )
    if args.verify_schema:
        expected_dim = infer_embedding_dim(args.embed_model, args.embed_dimensions)
        require_schema_match_for_embedding(client, args.collection, args.embed_field, expected_dim)
    embed_data(args, data)
    res = client.upsert(collection_name=args.collection, data=data)
    print_result({"upsert_result": str(res)})


def cmd_delete(client, args):
    if not args.confirm:
        print_error(
            "Confirmation required",
            "Refusing to delete without explicit confirmation.\n"
            f"Target collection: {args.collection!r}\n"
            f"Filter: {args.filter!r}\n"
            "Instruction: Run a preview query first and show the results to the user, then ask them to confirm.\n"
            f"1) data.py read --collection {args.collection} --filter {json.dumps(args.filter)} --limit {args.preview}\n"
            f"2) data.py delete --collection {args.collection} --filter {json.dumps(args.filter)} --confirm {json.dumps(args.filter)}",
        )
    if args.confirm != args.filter:
        print_error(
            "Confirmation mismatch",
            "--confirm must exactly match the --filter string used for deletion. "
            f"Expected {args.filter!r}, got {args.confirm!r}.",
        )
    res = client.delete(collection_name=args.collection, filter=args.filter)
    print_result({"delete_result": str(res)})


def cmd_search(client, args):
    data = parse_json_data(args.data)

    # Auto-embedding only (no direct vector queries).
    if not args.embed_model:
        print_error(
            "Auto-embedding required",
            "This CLI does not accept vector arrays for search.\n"
            "Instruction: pass a JSON array of query strings in --data (e.g. '[\"hello\"]') and set embedding config "
            "via MS_EMBEDDING_* env vars or pass --embed-provider/--embed-model (and optionally --embed-dimensions).",
        )
    if not all(isinstance(x, str) for x in data):
        print_error(
            "Invalid search input",
            "This CLI only supports text queries for search.\n"
            "Instruction: set --data to a JSON array of strings, e.g. '[\"find docs about AI\"]'.",
        )
    if args.verify_schema:
        expected_dim = infer_embedding_dim(args.embed_model, args.embed_dimensions)
        require_schema_match_for_embedding(client, args.collection, args.anns_field, expected_dim)
    embed_fn = get_embedding_model(args.embed_model, args.embed_provider, args.embed_base_url, args.embed_dimensions)
    data = embed_fn.encode_documents(data)

    kwargs = {
        "collection_name": args.collection,
        "data": data,
        "anns_field": args.anns_field,
        "limit": args.limit,
    }
    if args.filter:
        kwargs["filter"] = args.filter

    res = client.search(**kwargs)
    print_result(res)


def cmd_get(client, args):
    ids = parse_json_data(args.ids, "--ids")
    res = client.get(collection_name=args.collection, ids=ids)
    print_result(res)


# --- Shared embedding args ---

def add_embed_args(parser):
    """Add common embedding arguments to a subparser."""
    parser.add_argument("--embed-provider", default=os.environ.get("MS_EMBEDDING_PROVIDER", ""), help="Embedding provider ('openai' or 'volcengine')")
    parser.add_argument("--embed-model", default=os.environ.get("MS_EMBEDDING_MODEL", ""), help="Embedding model name")
    parser.add_argument("--embed-field", default="", help="Field to store generated vectors")
    parser.add_argument("--text-field", default="", help="Field containing raw text to embed")
    parser.add_argument("--embed-base-url", default=os.environ.get("MS_EMBEDDING_BASE_URL", ""), help="Optional base URL for embedding API")
    parser.add_argument(
        "--embed-dimensions",
        type=int,
        default=env_int("MS_EMBEDDING_DIMENSIONS"),
        help="Optional reduced embedding dimensions (requires model/provider support; default from MS_EMBEDDING_DIMENSIONS)",
    )
    verify = parser.add_mutually_exclusive_group()
    verify.add_argument(
        "--verify-schema",
        dest="verify_schema",
        action="store_true",
        default=True,
        help="Verify collection schema matches embedding config before auto-embedding (default: enabled)",
    )
    verify.add_argument(
        "--no-verify-schema",
        dest="verify_schema",
        action="store_false",
        help="Disable schema verification for auto-embedding",
    )


# --- Argument parser ---

def build_parser():
    parser = argparse.ArgumentParser(description="Milvus data plane CLI")
    parser.add_argument("--endpoint", required=True, help="Milvus server endpoint")
    parser.add_argument("--username", default="", help="Milvus username")
    parser.add_argument("--password", default="", help="Milvus password")

    sub = parser.add_subparsers(dest="command", required=True)

    # Collection management
    p = sub.add_parser("create_collection", help="Create a collection")
    p.add_argument("--collection", required=True, help="Collection name")
    p.add_argument("--dimension", type=int, default=None, help="Vector dimension (required unless using --schema-json/--schema-file)")
    p.add_argument("--primary-field-name", default="id", help="Primary key field name (default: id)")
    p.add_argument(
        "--id-type",
        default="int",
        choices=["int", "string"],
        help="Primary key type: int or string (default: int)",
    )
    # Default to auto-generated IDs to reduce user friction and avoid agents inventing IDs.
    # Users can opt out with --no-auto-id if they need deterministic external IDs.
    auto_id = p.add_mutually_exclusive_group()
    auto_id.add_argument(
        "--auto-id",
        dest="auto_id",
        action="store_true",
        default=True,
        help="Let Milvus auto-generate primary keys (default: enabled)",
    )
    auto_id.add_argument(
        "--no-auto-id",
        dest="auto_id",
        action="store_false",
        help="Disable auto-generated IDs; require the caller to provide primary keys explicitly",
    )
    p.add_argument("--vector-field-name", default="vector", help="Vector field name (default: vector)")
    p.add_argument(
        "--metric-type",
        default="COSINE",
        choices=["COSINE", "L2", "IP"],
        help="Vector metric type (default: COSINE)",
    )
    p.add_argument("--schema-json", default="", help="Custom schema as a JSON string (disables fast-create)")
    p.add_argument("--schema-file", default="", help="Path to a JSON file describing the custom schema (disables fast-create)")
    dyn = p.add_mutually_exclusive_group()
    dyn.add_argument(
        "--enable-dynamic-field",
        dest="enable_dynamic_field",
        action="store_true",
        default=False,
        help="Enable dynamic fields (default: disabled)",
    )
    dyn.add_argument(
        "--disable-dynamic-field",
        dest="enable_dynamic_field",
        action="store_false",
        default=False,
        help="Disable dynamic fields",
    )
    p.add_argument(
        "--pk-max-length",
        type=int,
        default=None,
        help="Max length for string primary keys (only when --id-type string)",
    )
    p.set_defaults(func=cmd_create_collection)

    p = sub.add_parser("drop_collection", help="Drop a collection")
    p.add_argument("--collection", required=True, help="Collection name")
    p.add_argument(
        "--confirm",
        default="",
        help="Required: must exactly match the collection name to proceed (safety confirmation)",
    )
    p.set_defaults(func=cmd_drop_collection)

    p = sub.add_parser("has_collection", help="Check if a collection exists")
    p.add_argument("--collection", required=True, help="Collection name")
    p.set_defaults(func=cmd_has_collection)

    p = sub.add_parser("list_collections", help="List all collections")
    p.set_defaults(func=cmd_list_collections)

    p = sub.add_parser("describe_collection", help="Describe a collection")
    p.add_argument("--collection", required=True, help="Collection name")
    p.set_defaults(func=cmd_describe_collection)

    # Data operations
    p = sub.add_parser("read", help="Query data with a filter expression")
    p.add_argument("--collection", required=True, help="Collection name")
    p.add_argument("--filter", required=True, help="Filter expression")
    p.add_argument("--limit", type=int, default=10, help="Result limit (default: 10)")
    p.set_defaults(func=cmd_read)

    p = sub.add_parser("insert", help="Insert data")
    p.add_argument("--collection", required=True, help="Collection name")
    p.add_argument("--data", required=True, help="JSON array of objects")
    add_embed_args(p)
    p.set_defaults(func=cmd_insert)

    p = sub.add_parser("upsert", help="Upsert data")
    p.add_argument("--collection", required=True, help="Collection name")
    p.add_argument("--data", required=True, help="JSON array of objects")
    add_embed_args(p)
    p.set_defaults(func=cmd_upsert)

    p = sub.add_parser("delete", help="Delete data")
    p.add_argument("--collection", required=True, help="Collection name")
    p.add_argument("--filter", required=True, help="Filter expression")
    p.add_argument(
        "--preview",
        type=int,
        default=5,
        help="Preview limit used in the required preview step with 'read' before deleting (default: 5)",
    )
    p.add_argument(
        "--confirm",
        default="",
        help="Required: must exactly match the filter string to proceed (safety confirmation)",
    )
    p.set_defaults(func=cmd_delete)

    p = sub.add_parser("search", help="Semantic search (text queries only; auto-embedding required)")
    p.add_argument("--collection", required=True, help="Collection name")
    p.add_argument("--data", required=True, help="JSON array of text strings (queries)")
    p.add_argument("--anns-field", required=True, help="Vector field to search")
    p.add_argument("--limit", type=int, default=10, help="Top-K results (default: 10)")
    p.add_argument("--filter", default="", help="Optional scalar filter")
    p.add_argument("--embed-provider", default=os.environ.get("MS_EMBEDDING_PROVIDER", ""), help="Embedding provider")
    p.add_argument("--embed-model", default=os.environ.get("MS_EMBEDDING_MODEL", ""), help="Embedding model (enables text-to-vector)")
    p.add_argument("--embed-base-url", default=os.environ.get("MS_EMBEDDING_BASE_URL", ""), help="Optional base URL for embedding API")
    p.add_argument(
        "--embed-dimensions",
        type=int,
        default=env_int("MS_EMBEDDING_DIMENSIONS"),
        help="Optional reduced embedding dimensions (requires model/provider support; default from MS_EMBEDDING_DIMENSIONS)",
    )
    verify = p.add_mutually_exclusive_group()
    verify.add_argument(
        "--verify-schema",
        dest="verify_schema",
        action="store_true",
        default=True,
        help="Verify collection schema matches embedding config before auto-embedding (default: enabled)",
    )
    verify.add_argument(
        "--no-verify-schema",
        dest="verify_schema",
        action="store_false",
        help="Disable schema verification for auto-embedding",
    )
    p.set_defaults(func=cmd_search)

    p = sub.add_parser("get", help="Get entities by primary key")
    p.add_argument("--collection", required=True, help="Collection name")
    p.add_argument("--ids", required=True, help="JSON array of IDs")
    p.set_defaults(func=cmd_get)

    return parser


def main():
    parser = build_parser()

    # Users (and agents) often append global flags after the subcommand, e.g.:
    #   data.py create_collection ... --endpoint ... --username ... --password ...
    # argparse requires "global" options to appear before the subcommand, unless we
    # normalize argv. Move known globals to the front while preserving relative order.
    argv = sys.argv[1:]
    global_flags = {"--endpoint", "--username", "--password"}
    extracted = []
    rest = []
    i = 0
    while i < len(argv):
        tok = argv[i]
        if tok in global_flags:
            extracted.append(tok)
            if i + 1 < len(argv):
                extracted.append(argv[i + 1])
                i += 2
                continue
        rest.append(tok)
        i += 1

    args = parser.parse_args(extracted + rest)
    client = connect(args)
    try:
        args.func(client, args)
    except Exception as e:
        msg = str(e)
        instr = ""
        if "Collection not found" in msg or "not exist" in msg:
            instr = "The Specified collection does not exist. Run 'list_collections' to see available collections, or 'create_collection' to create a new one."
        elif any(k in msg for k in ["schema", "dimension", "type", "value"]):
            instr = "Data or schema mismatch. Run 'describe_collection' to verify field names and vector dimensions."
        else:
            instr = "Verify your arguments and try again. For search/query, ensure you use valid filters like \"id > 0\"."

        details = f"{msg}\n\nInstruction: {instr}"
        print_error("Milvus Operation Error", details)


if __name__ == "__main__":
    main()
