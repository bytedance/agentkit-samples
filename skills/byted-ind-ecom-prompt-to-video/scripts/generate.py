import argparse
import json
import time
import requests
import os
from dotenv import load_dotenv
import logging
import base64
import mimetypes
from pathlib import Path
from urllib.parse import urlparse
import uuid
from tos_client import TOSClient

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

ARK_API_KEY = os.environ.get('ARK_API_KEY')
SEEDANCE_EP_ID = os.environ.get('SEEDANCE_EP_ID')
ARK_BASE_URL = os.environ.get('ARK_BASE_URL', 'https://ark.cn-beijing.volces.com/api/v3')
TOS_UPLOAD_ENABLED = os.environ.get('TOS_UPLOAD_ENABLED', 'true').lower() == 'true'


def _is_url(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _can_use_tos() -> bool:
    return all(
        [
            TOS_UPLOAD_ENABLED,
            os.environ.get("VOLC_ACCESS_KEY"),
            os.environ.get("VOLC_SECRET_KEY"),
            os.environ.get("TOS_ENDPOINT"),
            os.environ.get("TOS_BUCKET"),
        ]
    )


def _local_file_to_data_url(file_path: str) -> str:
    path = Path(file_path).expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(f"文件不存在: {path}")

    mime_type, _ = mimetypes.guess_type(str(path))
    mime_type = mime_type or "application/octet-stream"
    encoded = base64.b64encode(path.read_bytes()).decode("utf-8")
    return f"data:{mime_type};base64,{encoded}"


def _normalize_image_input(value: str) -> str:
    if _is_url(value):
        return value

    path = Path(value).expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(f"图片文件不存在: {path}")

    if _can_use_tos():
        tos_client = TOSClient()
        object_key = f"seedance_inputs/images/{uuid.uuid4().hex}_{path.name}"
        logger.info(f"Uploading local image to TOS: {path}")
        return tos_client.upload_file(str(path), object_key=object_key, public=True)

    logger.info(f"TOS unavailable, sending image as base64 data URL: {path}")
    return _local_file_to_data_url(str(path))


def _normalize_video_input(value: str) -> str:
    if _is_url(value):
        return value

    path = Path(value).expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(f"视频文件不存在: {path}")

    if not _can_use_tos():
        raise ValueError("本地参考视频需要公网 URL 或可用的 TOS 鉴权信息")

    tos_client = TOSClient()
    object_key = f"seedance_inputs/videos/{uuid.uuid4().hex}_{path.name}"
    logger.info(f"Uploading local video to TOS: {path}")
    return tos_client.upload_file(str(path), object_key=object_key, public=True)

def upload_video_to_tos(video_url, task_id):
    try:
        response = requests.get(video_url, stream=True)
        response.raise_for_status()
        
        file_name = f"seedance_videos/{task_id}.mp4"
        import tempfile
        with tempfile.NamedTemporaryFile(delete=False, suffix='.mp4') as temp_file:
            for chunk in response.iter_content(chunk_size=8192):
                temp_file.write(chunk)
            temp_file_path = temp_file.name

        tos_client = TOSClient()
        tos_url = tos_client.upload_file(temp_file_path, file_name, public=True)
        os.unlink(temp_file_path)
        return tos_url
    except Exception as e:
        logger.error(f"Upload to TOS failed: {e}")
        return None

def build_content(args):
    content = []
    
    if args.prompt:
        content.append({
            "type": "text",
            "text": args.prompt
        })
    
    if args.first_frame:
        content.append({
            "type": "image_url",
            "image_url": {"url": _normalize_image_input(args.first_frame)},
            "role": "first_frame"
        })
    
    if args.last_frame:
        content.append({
            "type": "image_url",
            "image_url": {"url": _normalize_image_input(args.last_frame)},
            "role": "last_frame"
        })
    
    if args.reference_images:
        for img_url in args.reference_images:
            content.append({
                "type": "image_url",
                "image_url": {"url": _normalize_image_input(img_url)},
                "role": "reference_image"
            })
            
    if args.reference_videos:
        for vid_url in args.reference_videos:
            content.append({
                "type": "video_url",
                "video_url": {"url": _normalize_video_input(vid_url)},
                "role": "reference_video"
            })
            
    return content

def generate_video(args):
    if not ARK_API_KEY:
        logger.error("ARK_API_KEY is not configured in .env")
        return
    if not SEEDANCE_EP_ID:
        logger.error("SEEDANCE_EP_ID is not configured in .env")
        return

    content = build_content(args)
    if not content:
        logger.error("No content provided. Please provide --prompt or image/video URLs.")
        return

    payload = {
        "model": SEEDANCE_EP_ID,
        "content": content,
    }

    optional_params = ['resolution', 'ratio', 'duration', 'frames', 'seed', 'camera_fixed', 'watermark', 'generate_audio', 'draft', 'return_last_frame', 'service_tier', 'execution_expires_after']
    args_dict = vars(args)
    for param in optional_params:
        if args_dict.get(param) is not None:
            payload[param] = args_dict[param]

    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {ARK_API_KEY}'
    }

    logger.info("Submitting task...")
    response = requests.post(
        f"{ARK_BASE_URL}/contents/generations/tasks",
        headers=headers,
        json=payload
    )

    if response.status_code != 200:
        logger.error(f"Failed to submit task: {response.status_code} - {response.text}")
        return

    result = response.json()
    task_id = result.get('id')
    if not task_id:
        logger.error("No task ID returned.")
        return

    logger.info(f"Task submitted successfully. Task ID: {task_id}")

    # Polling
    while True:
        logger.info(f"Polling task status for {task_id}...")
        status_response = requests.get(
            f"{ARK_BASE_URL}/contents/generations/tasks/{task_id}",
            headers=headers
        )

        if status_response.status_code != 200:
            logger.error(f"Failed to get task status: {status_response.status_code} - {status_response.text}")
            time.sleep(5)
            continue

        status_result = status_response.json()
        
        # handle case where status_result might not be what we expect
        if 'status' not in status_result and isinstance(status_result, dict):
            status = status_result.get('data', {}).get('status')
            if not status:
                status = status_result.get('status')
        else:
            status = status_result.get('status')
            
        logger.info(f"Current status: {status}")

        if status == 'succeeded':
            video_url = status_result.get('video_url')
            if not video_url and isinstance(status_result.get('content'), dict):
                video_url = status_result.get('content', {}).get('video_url')
                
            logger.info(f"Generation successful. Original Video URL: {video_url}")
            
            if video_url and _can_use_tos():
                logger.info("Uploading video to TOS...")
                tos_url = upload_video_to_tos(video_url, task_id)
                if tos_url:
                    logger.info(f"Successfully uploaded to TOS. Final URL: {tos_url}")
                    print(f"\nFinal Video URL: {tos_url}")
                else:
                    print(f"\nFailed to upload to TOS. Original Video URL: {video_url}")
            else:
                print(f"\nFinal Video URL: {video_url}")
                
            break
        elif status in ['failed', 'canceled']:
            logger.error(f"Task failed or canceled: {status_result.get('error')}")
            break

        time.sleep(5)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seedance 2.0 Video Generation CLI")
    parser.add_argument("--prompt", type=str, help="Text prompt")
    parser.add_argument("--first_frame", type=str, help="First frame image URL")
    parser.add_argument("--last_frame", type=str, help="Last frame image URL")
    parser.add_argument("--reference_images", type=str, nargs='*', help="Reference image URLs (up to 9)")
    parser.add_argument("--reference_videos", type=str, nargs='*', help="Reference video URLs (up to 3)")
    parser.add_argument("--resolution", type=str, help="Resolution")
    parser.add_argument("--ratio", type=str, help="Aspect ratio (e.g. 16:9)")
    parser.add_argument("--duration", type=int, help="Duration in seconds")
    parser.add_argument("--frames", type=int, help="Number of frames")
    parser.add_argument("--seed", type=int, help="Random seed")
    parser.add_argument("--camera_fixed", type=bool, help="Fixed camera")
    parser.add_argument("--watermark", type=bool, help="Include watermark")
    parser.add_argument("--generate_audio", type=bool, help="Generate audio")
    parser.add_argument("--draft", type=bool, help="Draft mode")
    parser.add_argument("--return_last_frame", type=bool, help="Return last frame")
    parser.add_argument("--service_tier", type=str, help="Service tier")
    parser.add_argument("--execution_expires_after", type=int, help="Execution expiration time")

    args = parser.parse_args()
    generate_video(args)
