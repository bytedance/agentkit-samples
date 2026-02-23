---
name: video-generate
description: Generate videos using Seedance models. Invoke when user wants to create videos from text prompts, images, or reference materials.
---

# Video Generate Skill

This skill generates videos using Doubao Seedance 1.0/1.5 models.

## Trigger Conditions

1. User wants to generate videos from text descriptions
2. User wants to create videos based on images (first/last frame)
3. User wants to create videos with reference materials (images, videos, audio)
4. User asks for video generation capabilities

## Usage

### Environment Variables

Before using this skill, ensure the following environment variables are set:

- `MODEL_VIDEO_API_KEY` or `MODEL_AGENT_API_KEY`: API key for the video generation service
- `MODEL_VIDEO_API_BASE`: API base URL (optional, has default)
- `MODEL_VIDEO_NAME`: Model name (optional, has default)

### Function Signature

```python
async def video_generate(
    params: list,
    batch_size: int = 10,
    max_wait_seconds: int = 1200,
    model_name: str = None,
) -> Dict:
```

### Parameters

#### params (list[dict])

A list of video generation requests. Each item is a dict with the following fields:

**Required per item:**

- `video_name` (str): Name/identifier of the output video file
- `prompt` (str): Text describing the video to generate. Supports Chinese and English.

**Optional per item - Input Materials:**

- `first_frame` (str): URL for the first frame image
- `last_frame` (str): URL for the last frame image
- `reference_images` (list[str]): 1-4 reference image URLs for style/content guidance
- `reference_videos` (list[str]): 0-3 reference video URLs (mp4/mov, 2-15s each, total ≤15s)
- `reference_audios` (list[str]): 0-3 reference audio URLs (mp3/wav, 2-15s each, total ≤15s)

**Optional per item - Video Output Parameters:**

- `ratio` (str): Aspect ratio. Options: "16:9" (default), "9:16", "4:3", "3:4", "1:1", "2:1", "21:9", "adaptive"
- `duration` (int): Video length in seconds. Range: 2-12s depending on model
- `resolution` (str): Video resolution. Options: "480p", "720p", "1080p"
- `frames` (int): Total frame count. Must be in [29, 289] and follow format 25 + 4n
- `camera_fixed` (bool): Lock camera movement. Default: false
- `seed` (int): Random seed for reproducibility. Range: [-1, 2^32-1]
- `watermark` (bool): Whether to add watermark. Default: false
- `generate_audio` (bool): Whether to generate audio. Only Seedance 1.5 supports this
- `tools` (list[dict]): Tool configuration, e.g., `[{"type": "web_search"}]`

### Input Modes

1. **Text-to-Video**: Only provide prompt, no images/videos
2. **First Frame Guidance**: Provide first_frame for starting image
3. **First + Last Frame Guidance**: Provide both for transition video
4. **Reference Images**: Provide reference_images for style/content guidance
5. **Multimodal Reference**: Combine reference_images, reference_videos, reference_audios

### Return Value

```python
{
    "status": "success" | "partial_success" | "error",
    "success_list": [{"video_name": "video_url"}],
    "error_list": ["video_name"],
    "error_details": [{"video_name": "...", "error": {...}}],
    "pending_list": [{"video_name": "...", "task_id": "cgt-xxx", ...}]
}
```

## Code Implementation

See [scripts/video_generate.py](scripts/video_generate.py) for the full implementation.

## Example Usage

```bash
# Text-to-Video
python scripts/video_generate.py -p "小猫骑着滑板穿过公园" -n cat_park -r 16:9 -d 5 --resolution 720p

# First Frame Guidance
python scripts/video_generate.py -p "小猫跳起来" -n cat_jump -f "https://example.com/cat.png" -r adaptive -d 5

# First + Last Frame Guidance
python scripts/video_generate.py -p "平滑过渡动画" -n transition \
    -f "https://example.com/start.png" \
    -l "https://example.com/end.png" \
    -d 6

# Reference Images (style/content guidance)
python scripts/video_generate.py -p "[图1]戴着眼镜的男生和[图2]柯基小狗坐在草坪上" -n styled \
    --ref-images "https://example.com/boy.png" "https://example.com/dog.png" \
    -r 16:9 -d 5

# Multimodal Reference (video + audio)
python scripts/video_generate.py -p "将视频中的人物换成[图1]中的男孩" -n multimodal \
    --ref-images "https://example.com/boy.png" \
    --ref-videos "https://example.com/source.mp4" \
    --ref-audios "https://example.com/voice.wav" \
    -d 5

# With Audio Generation (Seedance 1.5 only)
python scripts/video_generate.py -p "女孩抱着狐狸，可以听到风声和树叶沙沙声" -n with_audio \
    -f "https://example.com/girl_fox.png" \
    --generate-audio \
    -m doubao-seedance-1-5-pro-251215 \
    -d 6 --resolution 1080p

# Query task status
python scripts/video_generate.py -q "cgt-20260222165751-wsnw8"

# Use specific model
python scripts/video_generate.py -p "A futuristic city" -m doubao-seedance-1-5-pro-251215

# No watermark
python scripts/video_generate.py -p "A beautiful landscape" --no-watermark
```

### Command Line Options

| Option | Short | Description |
| -------- | ------- | ------------- |
| `--prompt` | `-p` | Text description of the video (required) |
| `--name` | `-n` | Video name identifier (default: video) |
| `--model` | `-m` | Model name (default: doubao-seedance-1-0-pro-250528) |
| `--ratio` | `-r` | Aspect ratio (default: 16:9) |
| `--duration` | `-d` | Video duration in seconds (2-12) |
| `--resolution` | | Video resolution: 480p, 720p, 1080p |
| `--first-frame` | `-f` | First frame image URL |
| `--last-frame` | `-l` | Last frame image URL |
| `--ref-images` | | Reference image URLs (space-separated, 1-4 images) |
| `--ref-videos` | | Reference video URLs (space-separated, 0-3 videos) |
| `--ref-audios` | | Reference audio URLs (space-separated, 0-3 audios) |
| `--generate-audio` | | Generate audio (Seedance 1.5 only) |
| `--seed` | | Random seed for reproducibility |
| `--no-watermark` | | Disable watermark |
| `--timeout` | `-t` | Max wait time in seconds (default: 1200) |
| `--query-task` | `-q` | Query task status by task_id |

## Model Fallback

If you encounter a model-related error (like `ModelNotOpen`), you can downgrade to these models:

- `doubao-seedance-1-5-pro-251215`
- `doubao-seedance-1-0-pro-250528`

## Notes

- Keep prompt concise (recommended ≤ 500 characters)
- For first/last frame, ensure aspect ratios match your chosen ratio
- Reference images: 1-4 images, formats: jpeg/png/webp/bmp/tiff/gif
- Reference videos: 0-3 videos, formats: mp4/mov, total duration ≤ 15s
- Reference audios: 0-3 audios, formats: mp3/wav, total duration ≤ 15s
- Multimodal requires at least one image or video (audio-only not supported)
- Audio generation is only supported by Seedance 1.5 pro
- If polling times out, use `--query-task` with the returned task_id
