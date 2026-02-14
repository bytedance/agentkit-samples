import argparse
import asyncio
import json
import os
import sys
from typing import List, Dict
from openai import AsyncOpenAI

async def evaluate_media_async(shots: List[Dict]) -> List[Dict]:
    """
    异步评估逻辑
    """
    api_key = os.getenv("MODEL_AGENT_API_KEY")
    if not api_key:
        # Fallback for local testing or if env var name differs
        api_key = os.getenv("OPENAI_API_KEY", "")
        
    client = AsyncOpenAI(
        base_url=os.getenv("MODEL_AGENT_API_BASE", "https://ark.cn-beijing.volces.com/api/v3"),
        api_key=api_key,
    )
    
    instruction = """
    你是一位专业的影视美术指导和影评人。请评估以下分镜画面的质量。
    
    评估维度：
    1. Visual Quality (视觉质量): 构图、光影、清晰度 (0-100分)
    2. Content Alignment (内容一致性): 画面是否符合 Prompt 描述 (0-100分)
    3. Style Consistency (风格一致性): 是否符合设定的艺术风格 (0-100分)
    
    请输出 JSON 格式：
    {
        "evaluation": {
            "scores": [visual_score, content_score, style_score],
            "reason": "简短的评审意见，指出优点和具体缺陷。"
        }
    }
    """

    async def process_shot(shot):
        prompt = shot.get("prompt", "")
        media_list = shot.get("media_list", [])
        reviewed_media = []
        
        for media in media_list:
            url = media.get("url")
            if not url:
                continue
            
            msg = {
                "role": "user",
                "content": [
                    {"type": "text", "text": f"请评估这张图片。Prompt: {prompt}"},
                    {"type": "image_url", "image_url": {"url": url}}
                ]
            }
            
            try:
                response = await client.chat.completions.create(
                    model=os.getenv("MODEL_EVALUATE_ITEM", "doubao-1-5-vision-pro-32k-250115"),
                    messages=[
                        {"role": "system", "content": instruction},
                        msg
                    ],
                    response_format={"type": "json_object"}
                )
                
                content = response.choices[0].message.content
                # Handle potential markdown code block wrapping
                if content.startswith("```json"):
                    content = content[7:-3]
                elif content.startswith("```"):
                    content = content[3:-3]
                    
                eval_data = json.loads(content)
                eval_info = eval_data.get("evaluation", {})
                scores = eval_info.get("scores", [0, 0, 0])
                avg_score = sum(scores) / len(scores) if scores else 0
                
                reviewed_media.append({
                    "id": media.get("id"),
                    "url": url,
                    "type": media.get("type", "image"),
                    "score": int(avg_score),
                    "feedback": eval_info.get("reason", "无反馈")
                })
            except Exception as e:
                # print(f"Error evaluating media {url}: {e}", file=sys.stderr)
                reviewed_media.append({
                    "id": media.get("id"),
                    "url": url,
                    "score": 0,
                    "feedback": f"评估失败: {str(e)}"
                })

        return {
            "shot_id": shot.get("shot_id"),
            "prompt": prompt,
            "media_list": reviewed_media
        }

    tasks = [process_shot(shot) for shot in shots]
    return await asyncio.gather(*tasks)

def calculate_total_score(reviewed_shots: List[Dict]) -> int:
    total = 0
    count = 0
    for shot in reviewed_shots:
        for media in shot.get("media_list", []):
            total += media.get("score", 0)
            count += 1
    return total // count if count > 0 else 0

def calculate_approval(reviewed_shots: List[Dict]) -> bool:
    scores = []
    for shot in reviewed_shots:
        for media in shot.get("media_list", []):
            scores.append(media.get("score", 0))
    
    if not scores:
        return False
        
    avg = sum(scores) / len(scores)
    min_score = min(scores)
    
    return avg >= 75 and min_score >= 50

def main():
    parser = argparse.ArgumentParser(description="Evaluate shots quality.")
    parser.add_argument("--project_id", type=str, required=True, help="Project ID")
    parser.add_argument("--shots", type=str, required=True, help="JSON string of shots")
    
    args = parser.parse_args()
    
    try:
        shots_data = json.loads(args.shots)
    except json.JSONDecodeError:
        print(json.dumps({"status": "error", "message": "Invalid JSON in shots argument"}))
        sys.exit(1)

    try:
        # Run async evaluation
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        evaluated_shots = loop.run_until_complete(evaluate_media_async(shots_data))
        
        final_result = {
            "status": "success",
            "project_id": args.project_id,
            "shots": evaluated_shots,
            "total_score": calculate_total_score(evaluated_shots),
            "is_approved": calculate_approval(evaluated_shots)
        }
        
        print(json.dumps(final_result, ensure_ascii=False))
        
    except Exception as e:
        print(json.dumps({"status": "error", "message": str(e)}))
        sys.exit(1)

if __name__ == "__main__":
    main()
