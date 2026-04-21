import sys
import json
import click
import logging
import requests
from urllib.parse import urlparse, parse_qs, urlencode
from base import Result, perror
from task import submit, poll


def simplify(url: str, keys: list) -> Result:
    try:
        # 校验域名
        parsed_original = urlparse(url)
        original_domain = parsed_original.netloc
        allowed_domains = ["haohuo.jinritemai.com", "v.douyin.com"]

        if original_domain not in allowed_domains:
            return Result(
                code="-1",
                message=f"URL域名不支持，仅支持以下域名：{', '.join(allowed_domains)}",
            )

        response = requests.head(url, allow_redirects=True)
        parsed = urlparse(response.url)
        query = {k: v for k, v in parse_qs(parsed.query).items() if k in keys}
        simplified_url = parsed._replace(query=urlencode(query, doseq=True)).geturl()
        return Result(code="0", message=simplified_url)
    except Exception as e:
        return Result(code="-1", message=f"简化URL失败：{str(e)}")


@click.command()
@click.option("--url", required=True, type=str, help="抖店商品链接")
@click.option("--output", required=True, type=str, help="输出结果所在的json文件路径")
def main(url, output):
    """调用创作云服务"""
    logging.info(f"[tool] >>> python3 {' '.join(sys.argv)}")

    simplify_res = simplify(url, ["id"])
    if simplify_res.code != "0":
        perror(simplify_res)
    print(f"简化URL成功，简化后的URL: {simplify_res.message}")

    submit_res = submit(
        3296206833079096, json.dumps({"url": simplify_res.message}, ensure_ascii=False)
    )
    if submit_res.code != "0":
        perror(submit_res)
    print(f"提交任务成功，任务ID: {submit_res.message}", flush=True)

    poll_res = poll(submit_res.message)
    if poll_res.code != "0":
        perror(poll_res)
    with open(output, "w") as f:
        result = json.loads(poll_res.message)
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(Result(code="0", message=output).model_dump_json())


if __name__ == "__main__":
    main()
