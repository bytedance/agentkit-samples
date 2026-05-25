# Comprehensive Quality Restoration `quality_enhance`

AI-based comprehensive video quality restoration: removes compression artifacts, noise, and scratches, improving overall clarity and color rendition.

## Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `type` | string | ✅ | `Vid` (video ID) or `DirectUrl` (VOD storage FileName) |
| `video` | string | ✅ | The video Vid or FileName (a `vid://` prefix is accepted and automatically stripped) |
| `config` | string | ✅ | VolcMoeEnhanceParam `Config`; one of `common`, `ugc`, `short_series`, `aigc`, `old_film`. If the user explicitly asks for defaults, use `common`. |
| `repair_style` | integer | ✅ | VolcMoeEnhanceParam `VideoStrategy.RepairStyle`; `1` = Standard, `2` = Pro. If the user explicitly asks for defaults, use `1`. |
| `res` | string | no | Optional `MoeEnhance.Target.Res`. **Omit** (or empty / `original`) to keep **source video resolution**. Allowed: `240p`, `360p`, `480p`, `540p`, `720p`, `1080p`, `2k`, `4k`. |

`config` and `repair_style` are required. If either value is missing from the user's request, ask the user to choose before submitting the job. Do not silently use defaults unless the user explicitly asks for default/recommended settings.

For **`res`**, ask whether they want **source resolution** (default — do not set `res`) or a specific target from the list above.

## Pro Allowlist Error Handling

If `repair_style=2` is used and the StartExecution/GetExecution response returns HTTP status `403`, or any error message contains `Permission denied`, it means the user has not been allowlisted for Pro. Pro is only available to users on the allowlist. Ask the user to submit a ticket to apply: https://console.byteplus.com/workorder/create

## Return Value

The job is automatically polled until a terminal state is reached. On success, it returns:

```json
{
  "Status": "Success",
  "SpaceName": "my_space",
  "VideoUrls": [
    {
      "FileId": "xxx",
      "DirectUrl": "path/to/output.mp4",
      "Source": "directurl://path/to/output.mp4",
      "Url": "https://example.cdn.com/path/to/output.mp4?auth_key=..."
    }
  ],
  "AudioUrls": [],
  "Texts": []
}
```

- `Url`: the script tries to produce a **directly accessible/downloadable** URL based on the space's play-domain configuration (it may carry auth parameters).
- `Source` (`directurl://...`) can be passed directly to downstream skills.

If polling times out, the response contains `error` + `resume_hint`, whose `command` can be used to resume polling:

```bash
uv run python scripts/poll_execution.py '<RunId>' [space_name]
```

## Examples

```bash
# Source resolution (no Target.Res)
uv run python scripts/quality_enhance.py '{"type":"Vid","video":"v0310abc","config":"common","repair_style":1}'

# Target 1080p output
uv run python scripts/quality_enhance.py '{"type":"Vid","video":"v0310abc","config":"common","repair_style":1,"res":"1080p"}'

# Use Pro tier with a different Moe config
uv run python scripts/quality_enhance.py '{"type":"Vid","video":"v0310abc","config":"ugc","repair_style":2}'

# Use DirectUrl as input
uv run python scripts/quality_enhance.py '{"type":"DirectUrl","video":"path/to/input.mp4","config":"common","repair_style":1}'

# Pass parameters via @file.json (recommended — avoids shell escaping issues)
uv run python scripts/quality_enhance.py @params.json

# Resume polling after a timeout
uv run python scripts/poll_execution.py 'run-xxx' my_space
```
