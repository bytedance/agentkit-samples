import os
import time
import logging
from pydantic import BaseModel
from dotenv import load_dotenv

__all__ = ["filename", "Result", "authentication"]
### 日志配置
filename = f"/tmp/openclaw/kickart/info.{time.strftime('%Y%m%d', time.localtime())}.log"
logging.basicConfig(
    level=logging.INFO,
    filename=filename,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
load_dotenv()


### 结果模型
class Result(BaseModel):
    code: str
    message: str
    data: object = None


def perror(res: Result):
    if res.code != "0":
        print(res.model_dump_json())
    exit(1)


### 判断使用那种鉴权方式
def authentication():
    ADDR = os.getenv("ARK_SKILL_API_BASE")
    TOKEN = os.getenv("ARK_SKILL_API_KEY")

    if ADDR is not None and TOKEN is not None:
        return 2

    ACCESS_KEY_ID = os.getenv("ACCESS_KEY_ID")
    SECRET_ACCESS_KEY = os.getenv("SECRET_ACCESS_KEY")
    if ACCESS_KEY_ID is not None and SECRET_ACCESS_KEY is not None:
        return 1
    return 0
