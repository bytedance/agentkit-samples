import argparse
from task import *

if __name__ == "__main__":
    logging.info(f"[tool] >>> python3 {' '.join(sys.argv)}")

    parser = argparse.ArgumentParser(description="故事板创作")
    parser.add_argument("--input", required=True, type=str, help="创意分析结果JSON文件路径")
    parser.add_argument("--output", required=True, type=str, help="输出结果所在的json文件路径")
    args = parser.parse_args()
 
    with open(args.input, "r") as f:
        creative = f.read()
    submit_res = submit(4337201517621323, creative)
    if submit_res.code != "0": perror(submit_res)
    print(f"提交任务成功，任务ID: {submit_res.message}", flush=True)

    poll_res = poll(submit_res.message)
    if poll_res.code != "0": perror(poll_res)
    with open(args.output, "w") as f:
        result = json.loads(poll_res.message)
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(Result(code="0", message=args.output).model_dump_json())
