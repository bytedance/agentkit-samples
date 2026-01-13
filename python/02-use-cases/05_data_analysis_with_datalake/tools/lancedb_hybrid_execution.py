import json
from typing import Optional

from rich.console import Console
import pandas as pd

# Import the LanceDBManager singleton
from .lancedb_manager import lancedb_manager

# Import utility functions
from .utils import get_multimodal_text_vector as _get_text_vector

console = Console()


def lancedb_hybrid_execution(
    query_text: str, filters: str = "", select: Optional[list] = None, limit: int = 10
) -> str:
    console.print(
        f"[lancedb_hybrid_execution] Inputs: query_text={query_text!r}, filters={filters!r}"
    )

    # open table
    tbl, err = lancedb_manager.open_table()
    if err:
        return json.dumps({"error": err}, ensure_ascii=False)

    # parse params
    vector_col = "poster_embedding"
    if select is None:
        select = ["Series_Title", "poster_precision_link"]

    # embed
    vec, v_err = _get_text_vector(query_text)
    if v_err:
        return json.dumps({"error": v_err}, ensure_ascii=False)

    # build search
    try:
        search_job = tbl.search(vec, vector_column_name=vector_col)
        if filters:
            # 直接使用模型生成的filter string
            filter_string = str(filters) if not isinstance(filters, str) else filters
            console.print(f"[hybrid] Applying filter: {filter_string}")
            search_job = search_job.where(filter_string)
        df: pd.DataFrame = search_job.limit(limit).to_pandas()
        present = [c for c in select if c in df.columns]
        if present:
            df = df[present]
        console.print(f"[hybrid] Returned rows: {len(df)}")
        header = [str(c).lower() for c in df.columns]
        try:
            df_norm = df.copy()
            df_norm.columns = header
            records_obj = df_norm.to_dict(orient="records")
        except Exception:
            records_obj = [
                {header[i]: row[i] for i in range(len(header))}
                for row in df.values.tolist()
            ]
        records = df.values.tolist()
        return json.dumps(
            {
                "status": "ok",
                "data": [header] + records,
                "records": records_obj,
                "meta": {"row_count": len(records)},
            },
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps({"error": f"混合检索失败: {e}"}, ensure_ascii=False)
