#!/bin/bash
# ==============================================================================
# 根据批处理目录生成 markdown 汇总
# Usage: scripts/generate_result.md.sh <run_dir>
# ==============================================================================

RUN_DIR="$1"
if [ -z "$RUN_DIR" ]; then
  echo "❌ 错误: 请提供 run_dir"
  exit 1
fi

SUMMARY_JSON="$RUN_DIR/summary.json"
SUMMARY_CSV="$RUN_DIR/summary.csv"

if [ ! -f "$SUMMARY_JSON" ]; then
  echo "❌ 错误: 未找到 $SUMMARY_JSON"
  exit 1
fi

SUCCESS_COUNT=$(python3 - <<PY
import json
from pathlib import Path
summary = json.loads(Path("$SUMMARY_JSON").read_text(encoding="utf-8"))
print(summary.get("success_count", 0))
PY
)
FAILURE_COUNT=$(python3 - <<PY
import json
from pathlib import Path
summary = json.loads(Path("$SUMMARY_JSON").read_text(encoding="utf-8"))
print(summary.get("failure_count", 0))
PY
)
PREVIEW=$(python3 - <<PY
import json
from pathlib import Path
summary = json.loads(Path("$SUMMARY_JSON").read_text(encoding="utf-8"))
for item in summary.get("results", []):
    if item.get("status") == "completed" and item.get("output_path"):
        text = Path(item["output_path"]).read_text(encoding="utf-8").strip()
        print(text[:500])
        break
PY
)

printf '%s\n' '# 本地批量 ASR 结果'
printf '\n'
printf '%s\n' '## 批处理信息'
printf '%s\n' "- 结果目录: $RUN_DIR"
printf '%s\n' "- 成功文件数: $SUCCESS_COUNT"
printf '%s\n' "- 失败文件数: $FAILURE_COUNT"
printf '%s\n' "- 汇总 JSON: $SUMMARY_JSON"
printf '%s\n' "- 汇总 CSV: $SUMMARY_CSV"
printf '\n'
printf '%s\n' '## 文本预览'
printf '\n'
printf '%s\n' "$PREVIEW"
printf '\n'
printf '%s\n' '## 建议下一步'
printf '%s\n' '- 如需入库，可将转写结果进一步抽取候选人画像后写入 byted-arkclaw-local-hr-crm'
printf '%s\n' '- 如需人工复核，优先查看 summary.csv 中失败项与对应 error 字段'
