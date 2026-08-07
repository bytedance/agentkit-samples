from rich.console import Console

# Import the LanceDBManager singleton
from .lancedb_manager import lancedb_manager

# Import utility functions
from .utils import dumps_json, get_text_embedding as get_embedding

console = Console()


def catalog_discovery(query_intent: str) -> str:
    """Search metadata using vector similarity based on the user's intent keywords."""
    console.print(f"[catalog_discovery] Inputs: query_intent={query_intent!r}")

    if not query_intent:
        return dumps_json(
            {
                "status": "error",
                "error": "Query intent is empty. Please provide a keyword to search.",
            }
        )

    tbl, error_msg = lancedb_manager.get_metadata_table()
    if error_msg:
        return dumps_json({"error": error_msg})

    try:
        # 调用方舟获取query condition的向量
        query_vector, emb_err = get_embedding(query_intent)
        if emb_err:
            console.print(
                f"[yellow]向量化失败，降级返回元数据表内容: {emb_err}[/yellow]"
            )
            results_df = tbl.to_pandas()
        else:
            # 调用Lance进行检索
            results_df = (
                tbl.search(query_vector, vector_column_name="vector")
                .limit(10)
                .to_pandas()
            )
        records = results_df.to_dict("records")

        # Remove the vector column from the records before returning to the agent
        for record in records:
            record.pop("vector", None)

        console.print(f"✅ 检索到 {len(records)} 条相关元数据")
        return dumps_json(
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
        return dumps_json({"status": "error", "error": error_msg})
