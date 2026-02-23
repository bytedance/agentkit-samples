---
name: image-generate
description: Generate images using Seedream models. Invoke when user wants to create images from text prompts or reference images.
---

# Image Generate Skill

This skill generates images using Doubao Seedream 4.0/4.5/5.0 models.

## Trigger Conditions

1. User wants to generate images from text descriptions
2. User wants to create images based on reference images
3. User asks for image generation capabilities

## Usage

### Environment Variables

Before using this skill, ensure the following environment variables are set:

- `MODEL_IMAGE_API_KEY` or `MODEL_AGENT_API_KEY`: API key for the image generation service
- `MODEL_IMAGE_API_BASE`: API base URL (optional, has default)
- `MODEL_IMAGE_NAME`: Model name (optional, has default)

### Function Signature

```python
async def image_generate(
    tasks: list[dict],
    timeout: int = 600,
    model_name: str = None,
) -> Dict:
```

### Parameters

#### tasks (list[dict])

A list of image-generation tasks. Each task is a dict with the following fields:

**Required:**

- `prompt` (str): Text description of the desired image(s). Chinese or English both work.
  To specify the number of images, add "生成N张图片" in the prompt.

**Optional:**

- `size` (str): Image size. Two formats:
  - Resolution level: "1K", "2K", "4K"
  - Exact dimensions: "<width>x<height>", e.g., "2048x2048", "2384x1728"
  - Default: "2048x2048"
  
- `response_format` (str): Return format. "url" (default, URL expires in 24h) or "b64_json"
- `watermark` (bool): Add watermark. Default: true
- `image` (str | list[str]): Reference image(s) as URL or Base64
  - For single image tasks: pass a string (exactly 1 image)
  - For group image tasks: pass an array (2-10 images)
- `sequential_image_generation` (str): Control group image generation. Default: "disabled"
  - Set to "auto" to generate multiple images
- `max_images` (int): Maximum number of images for group generation. Range [1, 15]
- `tools` (list[dict]): Tool configuration, e.g., `[{"type": "web_search"}]`
- `output_format` (str): Output format. "png" or "jpeg". Default: "jpeg"

### Task Types

The model infers the task type from parameters:

1. **Text to Single Image**: No `image`, `sequential_image_generation` not set or "disabled"
2. **Text to Group Images**: No `image`, `sequential_image_generation`="auto"
3. **Single Image to Single Image**: `image`=string, `sequential_image_generation` not set or "disabled"
4. **Single Image to Group Images**: `image`=string, `sequential_image_generation`="auto"
5. **Multi Image to Single Image**: `image`=array (2-10), `sequential_image_generation` not set or "disabled"
6. **Multi Image to Group Images**: `image`=array (2-10), `sequential_image_generation`="auto"

### Return Value

```python
{
    "status": "success" | "error",
    "success_list": [{"image_name": "url"}],
    "error_list": ["image_name"],
    "error_detail_list": [{"task_idx": 0, "error": {...}}]
}
```

## Code Implementation

See [scripts/image_generate.py](scripts/image_generate.py) for the full implementation.

## Example Usage

```bash
# Text to single image
python scripts/image_generate.py -p "A beautiful sunset over the ocean" -s 2048x2048

# Text to group images (generate 3 images)
python scripts/image_generate.py -p "生成3张可爱的小猫图片" -s 2K -g --max-images 3

# Image to image
python scripts/image_generate.py -p "Convert this image to anime style" -i "https://example.com/image.jpg"

# Multi-image to group images
python scripts/image_generate.py -p "Combine these images into a collage" --images "https://example.com/img1.jpg" "https://example.com/img2.jpg" -g --max-images 5

# Use specific model
python scripts/image_generate.py -p "A futuristic city" -m doubao-seedream-5-0-260128

# No watermark
python scripts/image_generate.py -p "A beautiful landscape" --no-watermark

# Output as PNG
python scripts/image_generate.py -p "A portrait photo" --output-format png
```

### Command Line Options

| Option | Short | Description |
| -------- | ------- | ------------- |
| `--prompt` | `-p` | Text description of the desired image(s) (required) |
| `--size` | `-s` | Image size (default: 2048x2048) |
| `--model` | `-m` | Model name (default: doubao-seedream-4-0-250828) |
| `--image` | `-i` | Single reference image URL |
| `--images` | | Multiple reference image URLs (space-separated) |
| `--group` | `-g` | Enable group image generation |
| `--max-images` | | Max images for group generation (default: 15) |
| `--output-format` | | Output format: png or jpeg (default: jpeg) |
| `--timeout` | `-t` | Timeout in seconds (default: 600) |
| `--no-watermark` | | Disable watermark |

## Model Fallback

If you encounter a model-related error (like `ModelNotOpen`), you can downgrade to these models:

- `doubao-seedream-5-0-260128`
- `doubao-seedream-4-5-251128`
- `doubao-seedream-4-0-250828`

## Notes

- Group image tasks require `sequential_image_generation="auto"`
- To specify the number of group images, add the count in the prompt (e.g., "生成3张图片")
- Recommended sizes: 2048x2048 or standard aspect ratios for best quality
- URL responses expire in 24 hours
