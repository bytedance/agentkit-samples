import argparse
import subprocess
from subprocess import DEVNULL
from task import *

if __name__ == "__main__":
    logging.info(f"[tool] >>> python3 {' '.join(sys.argv)}")

    parser = argparse.ArgumentParser(description="消费成片任务")
    parser.add_argument("--storyboard", required=False, type=int, default=0, help="用于成片任务的故事板编号")
    parser.add_argument("--session", required=True, type=str, help="当前Session的UUID，可用于openclaw agent指令的--session-id参数")
    parser.add_argument("--metadata", required=True, type=str, help="当前消息的完整未修改元信息")
    parser.add_argument("--input", required=True, type=str, help="故事板创作结果JSON文件路径")
    parser.add_argument("--output", required=True, type=str, help="输出结果所在的json文件路径")
    args = parser.parse_args()
    
    with open(args.input, "r") as f:
        data = json.load(f)

    storyboards = data['storyboards']
    if args.storyboard >= len(storyboards):
        perror(Result(code="-1", message=f"故事板编号超出范围，总故事板数为{len(storyboards)}, 请指定一个有效的故事板编号（1-{len(storyboards)}）"))
    
    data["storyboard"] = storyboards[args.storyboard]
    data["storyboards"] = None
    
    submit_res = submit(2935355633875543, json.dumps(data, ensure_ascii=False))
    if submit_res.code != "0": perror(submit_res)
    print(submit_res.model_dump_json(), flush=True)
    
    ### 创建后台轮询任务
    workspace = os.path.dirname(os.path.abspath(__file__))
    metadata = json.loads(args.metadata)
    cmd = ["bash", "poll.sh", submit_res.message, args.output, args.session, metadata['channel'], metadata['chat_id']]
    subprocess.Popen(cmd, cwd=workspace, text=True, start_new_session=True, stdin=DEVNULL, stdout=DEVNULL, stderr=DEVNULL)
