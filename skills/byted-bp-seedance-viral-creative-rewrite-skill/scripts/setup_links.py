# Copyright (c) 2026 BytePlus. All rights reserved.
# SPDX-License-Identifier: Proprietary
BYTEPLUS_REGISTRATION_URL = "https://console.byteplus.com/auth/signup?redirectURI=https%3A%2F%2Fwww.byteplus.com%2Fen&skipAccountProfile=true&utm_source=tiktok&utm_medium=lead-generation&utm_campaign=BP_TikTok_Agentic_Hub_FY26&utm_term=tiktok&utm_content=20260624"
MODELARK_API_KEY_URL = "https://console.byteplus.com/ark/region:ark+ap-southeast-1/apikey"
MODELARK_QUICK_START_URL = "https://docs.byteplus.com/zh-CN/docs/ModelArk/1399008"
SEEDANCE_RESOURCE_PACKAGE_URL = "https://docs.byteplus.com/zh-CN/docs/ModelArk/2191775"
SEEDANCE_TUTORIAL_URL = "https://docs.byteplus.com/zh-CN/docs/ModelArk/2291680"
VIDEO_GENERATION_TUTORIAL_URL = "https://docs.byteplus.com/zh-CN/docs/ModelArk/2298881"
VIDEO_GENERATION_API_URL = "https://docs.byteplus.com/zh-CN/docs/ModelArk/1520757"
MODEL_OPEN_MANAGEMENT_URL = "https://console.byteplus.com/ark/region:ark+ap-southeast-1/openManagement?LLM=%7B%7D"


def print_base_setup_links(language: str = "zh") -> None:
    if language == "en":
        print("\nUseful links:")
        print(f"- BytePlus registration: {BYTEPLUS_REGISTRATION_URL}")
        print(f"- ModelArk API Key management: {MODELARK_API_KEY_URL}")
        print(f"- ModelArk quick start: {MODELARK_QUICK_START_URL}")
        print("Note: real generation requires a Seedance 2.0 prepaid resource package or equivalent entitlement and video-generation permission.")
        return
    print("\n相关链接：")
    print(f"- BytePlus registration: {BYTEPLUS_REGISTRATION_URL}")
    print(f"- ModelArk API Key management: {MODELARK_API_KEY_URL}")
    print(f"- ModelArk quick start: {MODELARK_QUICK_START_URL}")
    print("提示：正式生成前需要先购买 Seedance 2.0 预付费资源包，并确认账号有视频生成权限。")


def print_real_generation_setup_flow(language: str = "zh") -> None:
    if language == "en":
        print("\nReal-generation setup:")
        print(f"1. Register a BytePlus account: {BYTEPLUS_REGISTRATION_URL}")
        print(f"2. Follow the ModelArk / Seedance flow to get an API key, buy the prepaid resource package, and activate Seedance video generation: {SEEDANCE_TUTORIAL_URL}")
        print(f"3. Open model management and enable Doubao Seed 2.0 Pro permission: {MODEL_OPEN_MANAGEMENT_URL}")
        return
    print("\n正式生成准备流程：")
    print(f"1. 注册 BytePlus 账号：{BYTEPLUS_REGISTRATION_URL}")
    print(f"2. 按 ModelArk / Seedance 流程获取 API Key、购买预付费资源包并激活 Seedance 视频生成模型：{SEEDANCE_TUTORIAL_URL}")
    print(f"3. 到模型开通管理页开启 Doubao Seed 2.0 Pro 模型权限：{MODEL_OPEN_MANAGEMENT_URL}")


def print_local_key_setup_hint(env_path: str, language: str = "zh") -> None:
    if language == "en":
        print("\nLocal configuration:")
        print("1. Get ARK_API_KEY from the ModelArk / Seedance setup flow above.")
        print(f"2. Create or edit .env in the skill root: {env_path}")
        print("3. Add this line: ARK_API_KEY=your_API_key")
        print("4. Do not paste the key into shared docs, logs, or chat messages.")
        return
    print("\n本地配置方式：")
    print("1. 按上面的 ModelArk / Seedance 流程拿到 ARK_API_KEY。")
    print(f"2. 在 skill 根目录创建或编辑 .env：{env_path}")
    print("3. 在 .env 里填写：ARK_API_KEY=你的_API_Key")
    print("4. 不要把 key 写进共享文档、日志或聊天记录。")
