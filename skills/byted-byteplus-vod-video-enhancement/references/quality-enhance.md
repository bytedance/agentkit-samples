# Comprehensive Quality Restoration `quality_enhance`

AI-based comprehensive video quality restoration: removes compression artifacts, noise, and scratches, improving overall clarity and color rendition.

Official references: [vCube upscaling and enhancement overview](https://docs.byteplus.com/en/docs/byteplus-vod/docs-video-enhancement#color-depth) and [Enhancing video quality via the OpenAPI](https://docs.byteplus.com/en/docs/byteplus-vod/vCube_enhancement_use_cases).

## Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `type` | string | ✅ | `Vid` (video ID) or `DirectUrl` (VOD storage FileName) |
| `video` | string | ✅ | The video Vid or FileName (a `vid://` prefix is accepted and automatically stripped) |
| `config` | string | ✅ | VolcMoeEnhanceParam `Config`; one of `common`, `ugc`, `short_series`, `aigc`, `old_film`. If the user explicitly asks for defaults, use `common`. |
| `repair_style` | integer | ✅ | VolcMoeEnhanceParam `VideoStrategy.RepairStyle`; `1` = Standard, `2` = Pro. If the user explicitly asks for defaults, use `1`. |
| `res` | string | no | Optional `MoeEnhance.Target.Res`. **Omit** (or empty / `original`) to keep **source video resolution**. Allowed: `240p`, `360p`, `480p`, `540p`, `720p`, `1080p`, `2k`, `4k`. |
| `bit_depth` | integer | no | Optional `MoeEnhance.Target.BitDepth`; supported only with Pro (`repair_style=2`). Online values: `8`, `10`, `12`, `16`. When omitted, the API default is `8`. |

`config` and `repair_style` are required. If either value is missing from the user's request, ask the user to choose before submitting the job. Do not silently use defaults unless the user explicitly asks for default/recommended settings.

For **`res`**, ask whether they want **source resolution** (default — do not set `res`) or a specific target from the list above.

For **`bit_depth`**, ask only when the user chooses Pro or explicitly requests color-depth control. The online API supports `8`, `10`, `12`, and `16`; omit the field to use the documented 8-bit default. An explicit color depth with Standard is invalid. 8-bit output uses H.264; 10-bit and 12-bit output use H.265; 16-bit output uses lossless FFV1.

### Color-depth usage limits

- Color-depth configuration is available only for the Pro enhancement tier and must be used as an advanced enhancement output setting.
- Online processing supports 8-bit, 10-bit, 12-bit, and 16-bit output.
- For 16-bit output, the input video must be **40 seconds or shorter**. Confirm the source duration before submitting because the script cannot derive it from the current arguments.
- 16-bit uses FFV1 lossless encoding, so no target bitrate should be configured. This skill does not expose or send a target bitrate.
- 16-bit tasks run serially, one task at a time. A new 16-bit task starts only after the current one completes, so processing can take longer.
- Ordinary players and SDR rendering pipelines may not correctly render 12-bit or 16-bit output. Use a color-managed professional tool such as DaVinci Resolve or Premiere and a compatible professional monitor for review.
- Use high-throughput storage such as a dedicated NVMe M.2 SSD for 16-bit lossless assets; ordinary hard drives or slow FAT32/exFAT disks can become a bottleneck.
- Conventional MP4/H.264/H.265 workflows are generally limited to 8-bit or 10-bit. For 12-bit delivery, the BytePlus documentation recommends MOV with H.265 `yuv444p12le` to avoid dithering or truncation.

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

# Pro tier with 10-bit H.265 output
uv run python scripts/quality_enhance.py '{"type":"Vid","video":"v0310abc","config":"ugc","repair_style":2,"bit_depth":10}'

# Pro tier with target resolution and color depth in the same Target object
uv run python scripts/quality_enhance.py '{"type":"Vid","video":"v0310abc","config":"aigc","repair_style":2,"res":"4k","bit_depth":12}'

# Pro tier with 16-bit FFV1 output (source must be 40 seconds or shorter)
uv run python scripts/quality_enhance.py '{"type":"Vid","video":"v0310abc","config":"aigc","repair_style":2,"bit_depth":16}'

# Use DirectUrl as input
uv run python scripts/quality_enhance.py '{"type":"DirectUrl","video":"path/to/input.mp4","config":"common","repair_style":1}'

# Pass parameters via @file.json (recommended — avoids shell escaping issues)
uv run python scripts/quality_enhance.py @params.json

# Resume polling after a timeout
uv run python scripts/poll_execution.py 'run-xxx' my_space
```
