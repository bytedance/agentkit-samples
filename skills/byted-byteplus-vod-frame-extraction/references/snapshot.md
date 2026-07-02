# BytePlus VOD Frame Extraction Reference

This skill wraps `StartExecution` (`Version=2025-07-01`) with `Operation.Type=Task`, `Task.Type=Snapshot` for frame extraction.

Official documentation: https://docs.byteplus.com/en/docs/byteplus-vod/reference-startexecution#operationtasksnapshot

## Request Shape

```json
{
  "SpaceName": "space",
  "Input": {
    "Type": "Vid",
    "Vid": "v0..."
  },
  "Operation": {
    "Type": "Task",
    "Task": {
      "Type": "Snapshot",
      "Snapshot": {
        "Strategy": {},
        "Target": {}
      }
    }
  }
}
```

`Input.Type` can be `Vid` or `DirectUrl`. For `DirectUrl`, the script uses the sibling VOD helper shape:

```json
{
  "Type": "DirectUrl",
  "DirectUrl": {
    "FileName": "path/in/vod/storage.mp4",
    "SpaceName": "space"
  }
}
```

## Supported Convenience Parameters

The script accepts a JSON object and builds `Snapshot` for common cases.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `type` | string | no | `Vid` or `DirectUrl`. Default: `Vid`. |
| `video` | string | yes | Vid or VOD `FileName`; `vid://` / `directurl://` prefixes are stripped automatically. |
| `strategy` / `strategy_type` / `mode` | string or object | no | `specified_time`, `interval`, `specified_frames`, or `scene_change`. Default: `specified_time`. If object, used directly as `Strategy`. |
| `times` / `time_ms` | integer or array | for specified time | Time offsets in milliseconds. Default: `[0]`. List length is limited to 1,000. |
| `interval_ms` / `interval` | integer | for interval | Snapshot interval in milliseconds; must be greater than 0. |
| `frames` | integer array | for specified frames | Frame indexes; `0` means first frame and `-1` means last frame. |
| `threshold` | float | for scene change | Scene-change detection threshold in `[0, 1]`. Default: `0.1`. |
| `resolution` | string | no | Snapshot resolution. Default: `720p`. Allowed: `240p`, `360p`, `480p`, `720p`, `1080p`. |
| `scale_long` | integer | no | Output long edge in pixels, [0, 4096]. |
| `scale_short` | integer | no | Output short edge in pixels, [0, 4096]. |
| `sprite` / `sprite_config` | boolean or object | no | If object, used directly as `SpriteConfig`; if true, sends `{ "Enable": true }` with optional `img_x_len` / `img_y_len`. |
| `output_mode` / `index_mode` | string | no | Maps to `IndexOption.Mode`: `Files` or `Index`. Omit for API default. |
| `target` | object | no | Used directly as `Target`, overriding `resolution` / scale convenience fields. |
| `snapshot` | object | no | Used directly as the complete `Snapshot` object. |
| `snapshot_options` | object | no | Deep-merged into the generated `Snapshot` object for advanced fields not surfaced above. |

## Strategy Examples

Specified time:

```json
{
  "type": "Vid",
  "video": "vid://v0xxx",
  "strategy": "specified_time",
  "times": [0, 5000, 10000],
  "resolution": "720p"
}
```

Fixed interval:

```json
{
  "type": "Vid",
  "video": "v0xxx",
  "strategy": "interval",
  "interval_ms": 3000,
  "resolution": "720p"
}
```

Specified frame indexes:

```json
{
  "type": "Vid",
  "video": "v0xxx",
  "strategy": "specified_frames",
  "frames": [0, 90, 180],
  "resolution": "720p"
}
```

Scene change:

```json
{
  "type": "Vid",
  "video": "v0xxx",
  "strategy": "scene_change",
  "threshold": 0.1,
  "resolution": "720p"
}
```

Direct full Snapshot passthrough:

```json
{
  "type": "Vid",
  "video": "v0xxx",
  "snapshot": {
    "Strategy": {
      "Type": "SpecifiedTime",
      "SpecifiedTime": {
        "Times": [0]
      }
    },
    "Target": {
      "Resolution": "720p"
    }
  }
}
```

## Output

On success, stdout contains one JSON object:

```json
{
  "Status": "Success",
  "SpaceName": "space",
  "ImageUrls": [
    {
      "FileId": "...",
      "Vid": "",
      "DirectUrl": "path/to/snapshot.jpg",
      "Source": "directurl://path/to/snapshot.jpg",
      "Url": "https://signed-playback-url",
      "Raw": {}
    }
  ],
  "VideoUrls": [],
  "AudioUrls": [],
  "Texts": [],
  "Snapshot": {}
}
```

`Snapshot` preserves the raw API output under `Output.Task.Snapshot`. `ImageUrls` is a best-effort normalization of file-like objects found in that output.
