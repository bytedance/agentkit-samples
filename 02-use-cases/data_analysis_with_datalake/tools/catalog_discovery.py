import json

from rich.console import Console

# Import the LanceDBManager singleton
from .lancedb_manager import lancedb_manager

# Import utility functions
from .utils import get_text_embedding as get_embedding

console = Console()


def catalog_discovery(query_intent: str) -> str:
    """Search metadata using vector similarity based on the user's intent keywords."""
    console.print(f"[catalog_discovery] Inputs: query_intent={query_intent!r}")

    if not query_intent:
        return json.dumps(
            {
                "status": "error",
                "error": "Query intent is empty. Please provide a keyword to search.",
            }
        )

    tbl, error_msg = lancedb_manager.get_metadata_table()
    if error_msg:
        return json.dumps({"error": error_msg})

    try:
        # 调用方舟获取query condition的向量
        query_vector, emb_err = get_embedding(query_intent)
        if emb_err:
            return json.dumps({"error": emb_err})

        # 调用Lance进行检索
        results_df = (
            tbl.search(query_vector, vector_column_name="vector").limit(10).to_pandas()
        )
        records = results_df.to_dict("records")

        # Remove the vector column from the records before returning to the agent
        for record in records:
            record.pop("vector", None)

        console.print(f"✅ 检索到 {len(records)} 条相关元数据")
        return json.dumps(
            {
                "status": "ok",
                "records": records,
                "meta": {"row_count": len(records)},
                "echo": {"query_intent": query_intent},
            }
        )
    except Exception as e:
        error_msg = f"❌ 检索失败: {e}"
        console.print(f"[red]{error_msg}[/red]")
        return json.dumps({"status": "error", "error": error_msg})
