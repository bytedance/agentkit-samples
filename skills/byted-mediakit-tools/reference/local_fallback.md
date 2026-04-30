# Local FFmpeg Fallback

`byted-mediakit-tools` includes `scripts/local_ffmpeg_tool.py` for local processing when cloud execution is unavailable or unsuitable.

## Routing Rules

The CLI chooses the backend automatically:

- Use AMK cloud when required cloud configuration and dependencies are complete and the command input is an `http://` or `https://` URL.
- Use local FFmpeg when a supported command receives a local file path.
- Use local FFmpeg when a supported command cannot use cloud execution because required cloud configuration or Python dependencies are missing.
- Keep cloud-only capabilities on AMK: `enhance_video`, `image_to_video`, `understand_video_content`, and `query_task`.
- Always use local FFmpeg for local-native commands: `flip-video`, `adjust-speed`, `add-subtitle`, `add-overlay`, and `transcode`.

Do not ask users to provide cloud environment variables for local-supported commands. The fallback path is intended to be invisible except for the JSON response fields such as `backend: "local_ffmpeg"` and a generic fallback reason.

## Local-Supported Commands

| AMK command | Local command | Notes |
| --- | --- | --- |
| `trim_media_duration --type video` | `trim-video` | Supports `--start_time`, `--end_time`, and optional `--output`. |
| `trim_media_duration --type audio` | `trim-audio` | Supports `--start_time`, `--end_time`, and optional `--output`. |
| `concat_media_segments --type video` | `concat-video` | Supports local/URL inputs. Cloud transition IDs are not mapped; use `--local_transition` for local xfade names. |
| `concat_media_segments --type audio` | `concat-audio` | Supports local/URL inputs and optional `--output`. |
| `extract_audio` | `extract-audio` | Supports `mp3` and `m4a` through the public wrapper; local tool can handle more formats directly. |
| `mux_audio_video` | `mux-audio-video` | `is_audio_reserve=true` maps to local mix mode; `false` maps to local replace mode. Local fallback does not support duration sync options. |
| `flip-video` / `flip_video` | `flip-video` | Local-only. Defaults to horizontal flip; supports `horizontal`, `vertical`, and `both`. |
| `adjust-speed` / `adjust_speed` | `adjust-speed` | Local-only. Uses FFmpeg `setpts` and `atempo`. |
| `add-subtitle` / `add_subtitle` | `add-subtitle` | Local-only hard subtitles for SRT/ASS. |
| `add-overlay` / `add_overlay` | `add-overlay` | Local-only image/watermark overlay with position, scale, and optional time range. |
| `transcode` | `transcode` | Local-only transcode/remux. Defaults to stream copy unless a codec is specified. |

## Examples

```bash
./byted-mediakit-tools.sh trim_media_duration \
  --type video \
  --source ./input.mp4 \
  --start_time 1 \
  --end_time 5 \
  --output ./trimmed.mp4
```

```bash
./byted-mediakit-tools.sh concat_media_segments \
  --type video \
  --sources ./a.mp4 ./b.mp4 \
  --output ./concat.mp4
```

```bash
./byted-mediakit-tools.sh mux_audio_video \
  --video_url ./video.mp4 \
  --audio_url ./audio.mp3 \
  --is_audio_reserve false \
  --output ./replaced.mp4
```

```bash
./byted-mediakit-tools.sh flip-video \
  -i ./input.mp4 \
  --direction horizontal \
  -o ./flipped.mp4
```

```bash
./byted-mediakit-tools.sh transcode \
  -i ./input.mov \
  --format mp4 \
  --codec h264 \
  -o ./output.mp4
```
