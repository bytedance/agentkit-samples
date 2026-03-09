import json

from rich.console import Console

# Import the LanceDBManager singleton
from .lancedb_manager import lancedb_manager

console = Console()


def duckdb_sql_execution(sql: str, user_question: str = "") -> str:
    """Execute structured SQL via DuckDB on Lance table contents.

    Expect sql to be a direct SQL string:
    "SELECT ..."
    """
    console.print(
        f"[duckdb_sql_execution] Inputs: sql={sql!r}, user_question={user_question!r}"
    )
    if not sql or not isinstance(sql, str):
        return json.dumps({"error": "SQL 字符串缺失或类型错误"}, ensure_ascii=False)

    # Open the table using the LanceDBManager
    tbl, err = lancedb_manager.open_table()
    if err:
        return json.dumps({"error": err}, ensure_ascii=False)

    view_name = "imdb_top_1000"

    # Register Arrow/Pandas to DuckDB
    conn = lancedb_manager.get_duckdb_connection()
    try:
        arrow_tbl = tbl.to_arrow()
        conn.register(view_name, arrow_tbl)
    except Exception:
        df = tbl.to_pandas()
        conn.register(view_name, df)

    # Execute SQL
    try:
        out_df = conn.execute(sql).fetchdf()
    except Exception as e:
        return json.dumps({"error": f"DuckDB 执行失败: {e}"}, ensure_ascii=False)

    # 构造 records（对象数组），并提供结构化响应
    header = [str(c) for c in out_df.columns]
    records_obj = out_df.to_dict(orient="records")

    records = out_df.values.tolist()
    try:
        console.print(f"[sql] Returned rows: {len(records)} from table='{view_name}'")
    except Exception:
        pass
    result = {
        "status": "ok",
        "data": [header] + records,
        "records": records_obj,
        "meta": {
            "row_count": len(records),
            "table": view_name,
        },
    }
    console.print(f"[duckdb_sql_execution] Result: {result}")
    return json.dumps(result, ensure_ascii=False)
