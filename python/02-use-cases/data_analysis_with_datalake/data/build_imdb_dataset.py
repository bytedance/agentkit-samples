#!/usr/bin/env python3
"""Build the local IMDb LanceDB dataset used by this sample."""

from __future__ import annotations

import argparse
import json
import os
import threading
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import lancedb
import pandas as pd
import pyarrow as pa
from dotenv import load_dotenv
from volcenginesdkarkruntime import Ark


SOURCE_URL = (
    "https://raw.githubusercontent.com/"
    "sayuricornejobarrantes/IMDB-PELICULAS/main/imdb_top_1000.csv"
)
DEFAULT_MULTIMODAL_MODEL = "doubao-embedding-vision-251215"
VECTOR_DIMENSIONS = 2048

DATA_DIR = Path(__file__).resolve().parent
PROJECT_DIR = DATA_DIR.parent
SOURCE_DIR = DATA_DIR / "source"
DB_DIR = DATA_DIR / "lance_catalog" / "default"
SOURCE_CSV = SOURCE_DIR / "imdb_top_1000.csv"
CHECKPOINT_FILE = DATA_DIR / "poster_embeddings.jsonl"
MANIFEST_FILE = DATA_DIR / "manifest.json"

_thread_local = threading.local()
_checkpoint_lock = threading.Lock()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workers", type=int, default=6)
    parser.add_argument("--force-download", action="store_true")
    parser.add_argument("--force-embeddings", action="store_true")
    return parser.parse_args()


def get_client() -> Ark:
    client = getattr(_thread_local, "client", None)
    if client is None:
        api_key = os.getenv("MODEL_AGENT_API_KEY")
        if not api_key:
            raise RuntimeError("MODEL_AGENT_API_KEY is required")
        base_url = os.getenv(
            "MODEL_AGENT_API_BASE",
            os.getenv("ARK_BASE_URL", "https://ark.cn-beijing.volces.com/api/v3"),
        )
        client = Ark(api_key=api_key, base_url=base_url)
        _thread_local.client = client
    return client


def extract_embedding(response: Any) -> list[float]:
    data = response.data
    item = data[0] if isinstance(data, (list, tuple)) else data
    vector = item.embedding
    if len(vector) != VECTOR_DIMENSIONS:
        raise ValueError(
            f"unexpected embedding dimension: {len(vector)}, "
            f"expected {VECTOR_DIMENSIONS}"
        )
    return [float(value) for value in vector]


def multimodal_embedding(item: dict[str, Any]) -> list[float]:
    model = os.getenv("ARK_MULTIMODAL_EMBEDDING_MODEL", DEFAULT_MULTIMODAL_MODEL)
    response = get_client().multimodal_embeddings.create(
        model=model,
        input=[item],
        encoding_format="float",
        dimensions=VECTOR_DIMENSIONS,
    )
    return extract_embedding(response)


def with_retry(operation, attempts: int = 5):
    error: Exception | None = None
    for attempt in range(attempts):
        try:
            return operation()
        except Exception as exc:
            error = exc
            if attempt + 1 < attempts:
                time.sleep(min(2**attempt, 10))
    assert error is not None
    raise error


def download_source(force: bool) -> None:
    SOURCE_DIR.mkdir(parents=True, exist_ok=True)
    if SOURCE_CSV.exists() and not force:
        return
    request = urllib.request.Request(
        SOURCE_URL, headers={"User-Agent": "volcengine-agentkit-samples"}
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        SOURCE_CSV.write_bytes(response.read())


def precision_poster_url(url: str) -> str:
    marker = "._V1_"
    if marker not in url:
        return url
    return f"{url.split(marker, 1)[0]}._V1_.jpg"


def load_movies() -> pd.DataFrame:
    frame = pd.read_csv(SOURCE_CSV)
    if len(frame) != 1000:
        raise ValueError(f"expected 1000 movies, found {len(frame)}")
    frame.columns = [column.lower() for column in frame.columns]

    string_columns = [
        "poster_link",
        "series_title",
        "released_year",
        "certificate",
        "runtime",
        "genre",
        "overview",
        "director",
        "star1",
        "star2",
        "star3",
        "star4",
    ]
    for column in string_columns:
        frame[column] = frame[column].fillna("").astype(str)

    frame["imdb_rating"] = pd.to_numeric(frame["imdb_rating"], errors="coerce").astype(
        "float64"
    )
    frame["meta_score"] = pd.to_numeric(frame["meta_score"], errors="coerce").astype(
        "float64"
    )
    frame["no_of_votes"] = pd.to_numeric(frame["no_of_votes"], errors="coerce").astype(
        "Int64"
    )
    frame["gross"] = pd.to_numeric(
        frame["gross"].astype(str).str.replace(",", "", regex=False),
        errors="coerce",
    ).astype("Int64")

    frame["poster_curde_link"] = frame["poster_link"]
    frame["poster_precision_link"] = frame["poster_link"].map(precision_poster_url)
    frame["_source_index"] = frame.index.astype(int)
    return frame


def load_checkpoint(force: bool) -> dict[int, dict[str, Any]]:
    if force or not CHECKPOINT_FILE.exists():
        return {}
    records: dict[int, dict[str, Any]] = {}
    for line in CHECKPOINT_FILE.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        record = json.loads(line)
        records[int(record["index"])] = record
    return records


def fallback_text(row: pd.Series) -> str:
    return (
        f"Movie poster for {row['series_title']}. "
        f"Genre: {row['genre']}. Director: {row['director']}. "
        f"Plot: {row['overview']}"
    )


def embed_poster(index: int, row: pd.Series) -> dict[str, Any]:
    url = row["poster_precision_link"]
    try:
        vector = with_retry(
            lambda: multimodal_embedding(
                {"type": "image_url", "image_url": {"url": url}}
            )
        )
        mode = "image"
        error = None
    except Exception as image_error:
        vector = with_retry(
            lambda: multimodal_embedding({"type": "text", "text": fallback_text(row)})
        )
        mode = "text_fallback"
        error = str(image_error)

    record = {
        "index": index,
        "title": row["series_title"],
        "mode": mode,
        "error": error,
        "vector": vector,
    }
    with _checkpoint_lock:
        with CHECKPOINT_FILE.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(record, ensure_ascii=False) + "\n")
    return record


def build_poster_embeddings(
    frame: pd.DataFrame, workers: int, force: bool
) -> tuple[list[list[float]], int]:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if force and CHECKPOINT_FILE.exists():
        CHECKPOINT_FILE.unlink()
    records = load_checkpoint(force)
    source_indices = frame["_source_index"].astype(int).tolist()
    pending = [
        (int(row["_source_index"]), row)
        for _, row in frame.iterrows()
        if int(row["_source_index"]) not in records
    ]
    cached = sum(index in records for index in source_indices)
    print(f"Poster embeddings: {cached} cached, {len(pending)} pending")

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {
            executor.submit(embed_poster, index, row): index for index, row in pending
        }
        completed = 0
        for future in as_completed(futures):
            record = future.result()
            records[int(record["index"])] = record
            completed += 1
            if completed % 25 == 0 or completed == len(pending):
                print(f"  completed {completed}/{len(pending)}")

    vectors = [records[index]["vector"] for index in source_indices]
    fallback_count = sum(records[index]["mode"] != "image" for index in source_indices)
    return vectors, fallback_count


def metadata_rows(frame: pd.DataFrame) -> list[dict[str, str]]:
    descriptions = {
        "poster_link": "Original IMDb movie poster URL.",
        "series_title": "Movie title.",
        "released_year": "Release year stored as text.",
        "certificate": "Audience certificate or content rating.",
        "runtime": "Movie runtime, such as 142 min.",
        "genre": "Comma-separated movie genres.",
        "imdb_rating": "IMDb audience rating.",
        "overview": "Short plot summary.",
        "meta_score": "Metacritic score.",
        "director": "Movie director.",
        "star1": "First principal cast member.",
        "star2": "Second principal cast member.",
        "star3": "Third principal cast member.",
        "star4": "Fourth principal cast member.",
        "no_of_votes": "Number of IMDb audience votes.",
        "gross": "Reported gross box office revenue in US dollars.",
        "poster_curde_link": "Thumbnail poster URL.",
        "poster_precision_link": "Higher-resolution poster URL.",
        "poster_embedding": "2048-dimensional multimodal poster embedding.",
    }
    rows = []
    for column, description in descriptions.items():
        if column == "poster_embedding":
            data_type = "fixed_size_list<float32>[2048]"
            samples = ["multimodal vector"]
        else:
            data_type = str(frame[column].dtype)
            samples = [
                None if pd.isna(value) else value
                for value in frame[column].head(3).tolist()
            ]
        rows.append(
            {
                "table_name": "imdb_top_1000",
                "column_name": column,
                "data_type": data_type,
                "description": description,
                "sample_values": json.dumps(samples, ensure_ascii=False),
            }
        )
    return rows


def build_metadata_embeddings(
    rows: list[dict[str, str]], workers: int
) -> list[list[float]]:
    def embed(row: dict[str, str]) -> list[float]:
        text = (
            f"Table {row['table_name']}; column {row['column_name']}; "
            f"type {row['data_type']}; {row['description']}; "
            f"samples {row['sample_values']}"
        )
        return with_retry(lambda: multimodal_embedding({"type": "text", "text": text}))

    with ThreadPoolExecutor(max_workers=min(workers, len(rows))) as executor:
        return list(executor.map(embed, rows))


def replace_table(db, name: str, table: pa.Table) -> None:
    existing = set(db.table_names())
    if name in existing:
        db.drop_table(name)
    db.create_table(name, table)


def write_lance_tables(
    frame: pd.DataFrame,
    poster_vectors: list[list[float]],
    metadata: list[dict[str, str]],
    metadata_vectors: list[list[float]],
) -> None:
    DB_DIR.mkdir(parents=True, exist_ok=True)
    db = lancedb.connect(DB_DIR)

    movie_table = pa.Table.from_pandas(frame, preserve_index=False)
    movie_table = movie_table.append_column(
        "poster_embedding",
        pa.array(
            poster_vectors,
            type=pa.list_(pa.float32(), VECTOR_DIMENSIONS),
        ),
    )
    replace_table(db, "imdb_top_1000", movie_table)

    metadata_frame = pd.DataFrame(metadata)
    metadata_table = pa.Table.from_pandas(metadata_frame, preserve_index=False)
    metadata_dimension = len(metadata_vectors[0])
    metadata_table = metadata_table.append_column(
        "vector",
        pa.array(
            metadata_vectors,
            type=pa.list_(pa.float32(), metadata_dimension),
        ),
    )
    replace_table(db, "metadata_table", metadata_table)


def write_manifest(
    frame: pd.DataFrame,
    fallback_count: int,
    metadata_vectors: list[list[float]],
) -> None:
    manifest = {
        "created_at": datetime.now(UTC).isoformat(),
        "source_url": SOURCE_URL,
        "database_root": str(DB_DIR.relative_to(DATA_DIR)),
        "tables": {
            "imdb_top_1000": {
                "rows": len(frame),
                "vector_column": "poster_embedding",
                "vector_dimension": VECTOR_DIMENSIONS,
                "image_embeddings": len(frame) - fallback_count,
                "text_fallback_embeddings": fallback_count,
            },
            "metadata_table": {
                "rows": 19,
                "vector_column": "vector",
                "vector_dimension": len(metadata_vectors[0]),
            },
        },
        "models": {
            "poster_embedding": os.getenv(
                "ARK_MULTIMODAL_EMBEDDING_MODEL", DEFAULT_MULTIMODAL_MODEL
            ),
            "metadata_embedding": os.getenv(
                "ARK_MULTIMODAL_EMBEDDING_MODEL", DEFAULT_MULTIMODAL_MODEL
            ),
        },
    }
    MANIFEST_FILE.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def verify() -> None:
    db = lancedb.connect(DB_DIR)
    names = sorted(db.table_names())
    if names != ["imdb_top_1000", "metadata_table"]:
        raise RuntimeError(f"unexpected tables: {names}")

    movies = db.open_table("imdb_top_1000")
    metadata = db.open_table("metadata_table")
    if movies.count_rows() != 1000:
        raise RuntimeError(f"unexpected movie row count: {movies.count_rows()}")
    if metadata.count_rows() != 19:
        raise RuntimeError(f"unexpected metadata row count: {metadata.count_rows()}")

    movie_probe = (
        movies.search(
            movies.to_arrow()["poster_embedding"][0].as_py(),
            vector_column_name="poster_embedding",
        )
        .limit(1)
        .to_pandas()
    )
    metadata_probe = (
        metadata.search(
            metadata.to_arrow()["vector"][0].as_py(),
            vector_column_name="vector",
        )
        .limit(1)
        .to_pandas()
    )
    print(f"Tables: {names}")
    print(
        f"Movie rows: {movies.count_rows()}; "
        f"probe: {movie_probe.iloc[0]['series_title']}"
    )
    print(
        "Metadata rows: "
        f"{metadata.count_rows()}; probe: {metadata_probe.iloc[0]['column_name']}"
    )


def main() -> None:
    load_dotenv(PROJECT_DIR / ".env", override=False)
    load_dotenv(PROJECT_DIR / "settings.txt", override=False)
    args = parse_args()

    download_source(args.force_download)
    selected_frame = load_movies()
    poster_vectors, fallback_count = build_poster_embeddings(
        selected_frame, args.workers, args.force_embeddings
    )
    frame = selected_frame.drop(columns=["_source_index"])
    metadata = metadata_rows(frame)
    metadata_vectors = build_metadata_embeddings(metadata, args.workers)
    write_lance_tables(frame, poster_vectors, metadata, metadata_vectors)
    write_manifest(frame, fallback_count, metadata_vectors)
    verify()
    print(f"Dataset ready at: {DATA_DIR}")


if __name__ == "__main__":
    main()
