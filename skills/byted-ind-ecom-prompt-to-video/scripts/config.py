import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

class Config:
    # 同步现有的环境变量名
    VOLC_AK = os.getenv("VOLC_ACCESS_KEY")
    VOLC_SK = os.getenv("VOLC_SECRET_KEY")

    TOS_ENDPOINT = os.getenv("TOS_ENDPOINT")
    TOS_REGION = os.getenv("TOS_REGION", "cn-beijing")
    TOS_BUCKET = os.getenv("TOS_BUCKET")

    ASSET_AK = os.getenv("ASSET_ACCESS_KEY")
    ASSET_SK = os.getenv("ASSET_SECRET_KEY")
    ASSET_TOS_ENDPOINT = os.getenv("ASSET_TOS_ENDPOINT", TOS_ENDPOINT)
    ASSET_TOS_REGION = os.getenv("ASSET_TOS_REGION", TOS_REGION)
    ASSET_TOS_BUCKET = os.getenv("ASSET_TOS_BUCKET")

config = Config()
