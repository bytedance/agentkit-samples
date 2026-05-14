# precise_erase（`scripts/precise_erase.py`）

异步 **precision erasure**（`OperationTaskErase`，经 `precise_erase.py` 封装）。能力与请求字段可参考 [BytePlus VOD — precision subtitle erasure](https://docs.byteplus.com/en/docs/byteplus-vod/docs-precision-subtitle-erasure) 与本文所在 skill 仓库 `SKILL.md`。

**实现约定（与 skill 对齐）：**

- **Mode：** 请求中恒为 **`Auto`** — 不向用户暴露其它 mode。
- **NewVid：** 恒为 **`true`**，不可由 JSON 配置。
- **字幕 vs 全画面文字：** 默认 **字幕**（`Subtitle` + `SubtitleFilter {}`）。用户勾选「全文/全画面文字」时用 `text: true` 或 `all_text: true` → `Auto.Type = Text`。
- **整段：** 默认不传 `clip_filter`，不发送 `EraseOption.ClipFilter`。
- **片段：** 可选 `clip_filter`，**`mode`** 为 `skip` 或 `selected` 时 **`clips` 必填**（非空）。请求体中会转为 API 的 `Skip` / `Selected` 与 `Start` / `End`。
- **`WithEraseInfo`：** 默认 `true`；`with_erase_info: false` 时 API 不传详细擦除信息，stdout 中 `EraseMeta` 为 `{}`；仍解析 `Erase.File` 得到 `VideoUrls`。

## 参数（`json_args`）

| 参数 | 必填 | 说明 |
|------|------|------|
| `type` | ✅ | `Vid` 或 `DirectUrl` |
| `video` | ✅ | Vid 或 VOD `FileName`；自动去掉 `vid://` / `directurl://` |
| `text` | 否 | 为 true 时擦除 **字幕 + 其它画面文字**（`Text`）。默认 false 为仅字幕。 |
| `all_text` | 否 | 与 **`text`** 同义；同时存在时先读 **`text`**。 |
| `clip_filter` | 否 | 缺省为整段。若提供：需 **`mode`** `skip` \| `selected`，且 **`clips`** 至少一段 `{ "start", "end" }` 秒（或 `Start`/`End`）。 |
| `with_erase_info` | 否 | 默认 `true`；`false` 时 API `WithEraseInfo` 为 false。 |

禁止 / 忽略：**`mode`（手动等）**、**`new_vid`**。

## CLI 示例

```bash
uv run python scripts/precise_erase.py '{"type":"Vid","video":"v0310abc"}'
uv run python scripts/precise_erase.py '{"type":"Vid","video":"v0310abc","text":true}'
uv run python scripts/precise_erase.py '{"type":"Vid","video":"v0310abc","clip_filter":{"mode":"selected","clips":[{"start":10,"end":60}]}}'
uv run python scripts/precise_erase.py '{"type":"Vid","video":"v0310abc","clip_filter":{"mode":"skip","clips":[{"start":0,"end":15}]}}'
uv run python scripts/precise_erase.py '{"type":"Vid","video":"v0310abc","with_erase_info":false}'
```

Skill 根目录名：**`byted-byteplus-vod-precision-erasure`**。
