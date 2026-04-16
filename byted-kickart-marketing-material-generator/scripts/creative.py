import argparse
import json
from collections import defaultdict
import media
from task import *

def concat(args)->dict:
    material = defaultdict()
    if args.input:
        with open(args.input, "r") as f:
            material = json.load(f)
    material["video_duration"] = args.duration
    material["user_prompt"] = args.prompt

    if args.session_id:
        materials = media.list(args)
        material["user_images"] = [m for m in materials if m['type'] == "image"]
        material["user_videos"] = [m for m in materials if m['type'] == "video"]
    return material

def check(args)->Result:
    if args.duration < 0 or args.duration > 60:
        return Result(code="-1", message="视频时长必须在0-60秒之间", data=None)
    return Result(code="0", message="success", data=None)

if __name__ == "__main__":
    logging.info(f"[tool] >>> python3 {' '.join(sys.argv)}")

    parser = argparse.ArgumentParser(description="创意分析服务")
    parser.add_argument("--input", required=False, type=str, help="素材分析结果JSON文件路径")
    parser.add_argument("--session-id", required=False, type=str, help="已上传的远程素材列表对应的会话ID")
    parser.add_argument("--duration", required=False, type=int, default=15, help="自定义时长，默认15秒")
    parser.add_argument("--prompt", required=False, type=str, default="无人物出镜", help="自定义提示，默认无人物出镜")
    parser.add_argument("--output", required=True, type=str, help="输出结果所在的json文件路径")
    args = parser.parse_args()
    
    material = json.dumps(concat(args), ensure_ascii=False)

    check_res = check(args)
    if check_res.code != "0": perror(check_res)


    submit_res = submit(3339986037439799, material)
    if submit_res.code != "0": perror(submit_res)
    print(f"提交任务成功，任务ID: {submit_res.message}", flush=True)

    poll_res = poll(submit_res.message)
    if poll_res.code != "0": perror(poll_res)
    with open(args.output, "w") as f:
        result = json.loads(poll_res.message)
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(Result(code="0", message=args.output).model_dump_json())
