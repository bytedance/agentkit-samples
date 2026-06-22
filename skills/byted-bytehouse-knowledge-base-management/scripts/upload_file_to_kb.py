#!/usr/bin/env python3
# Copyright (c) 2025 Beijing Volcano Engine Technology Co., Ltd. and/or its affiliates.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
ByteHouse 知识库文件上传脚本
用于上传文件到ByteHouse知识库并自动进行切片处理
支持格式：md, txt, pdf, docx, xlsx, csv等

配置方式：设置以下环境变量
- BYTEHOUSE_HOST: ByteHouse 主机地址 (如 tenant-xxx-cn-beijing-public.bytehouse.volces.com)
- BYTEHOUSE_PASSWORD: 密码 (用作 Bearer token)
"""

import os
import requests
import json
import sys
import argparse
import os.path

# 从环境变量读取默认配置
BYTEHOUSE_HOST = os.environ.get('BYTEHOUSE_HOST', '')
BYTEHOUSE_PASSWORD = os.environ.get('BYTEHOUSE_PASSWORD', '')

def get_auth_headers() -> dict:
    """获取公共请求头"""
    headers = {
        "Content-Type": "application/json",
    }
    if BYTEHOUSE_PASSWORD:
        headers["Authorization"] = f"Bearer {BYTEHOUSE_PASSWORD}"
    return headers


def build_kb_api_url(host: str, endpoint: str) -> str:
    """构建知识库API URL"""
    if not host:
        print("Error: BYTEHOUSE_HOST environment variable is required", file=sys.stderr)
        sys.exit(1)
    
    # 处理 host - 可能是 host:port 格式
    if host.startswith('http'):
        base_url = host.rstrip('/')
    else:
        base_url = f"https://{host}"
    
    return f"{base_url}/matrix/v1/{endpoint.lstrip('/')}"


def generate_upload_url(
    kb_id: int, 
    file_name: str, 
    file_size: int
) -> tuple[str, str, str, dict]:
    """
    生成文件上传预签名URL
    
    Args:
        kb_id: 知识库ID
        file_name: 文件名
        file_size: 文件大小（字节）
    
    Returns:
        (file_id, upload_url, upload_method, upload_headers)
    """
    if not BYTEHOUSE_HOST:
        print("Error: Please set BYTEHOUSE_HOST environment variable", file=sys.stderr)
        sys.exit(1)
    
    url = build_kb_api_url(BYTEHOUSE_HOST, 'knowledge-base/file/generate-upload-files-url')
    headers = get_auth_headers()
    
    # 构建请求 payload
    payload = {
        "knowledgeBaseID": kb_id,
        "files": [
            {
                "name": file_name,
                "sizeBytes": file_size
            }
        ]
    }
    
    response = requests.post(url, headers=headers, json=payload, timeout=30)
    response.raise_for_status()
    
    result = response.json()
    data_list = result.get('data', [])
    file_info = data_list[0] if isinstance(data_list, list) and data_list else {}
    
    file_id = file_info.get('fileID')
    upload_url = file_info.get('url')
    upload_method = file_info.get('method', 'PUT')
    upload_headers_raw = file_info.get('headers', {})

    upload_headers = {}
    for k, v in upload_headers_raw.items():
        if not v:
            continue
        if isinstance(v, (list, tuple)):
            upload_headers[k] = v[0]
        else:
            upload_headers[k] = v
    
    if not file_id or not upload_url:
        print(f"Error: Failed to get upload URL from response: {result}", file=sys.stderr)
        sys.exit(1)
    
    return file_id, upload_url, upload_method, upload_headers


def upload_file(upload_url: str, upload_method: str, upload_headers: dict, file_path: str) -> None:
    """上传文件到预签名URL"""
    with open(file_path, 'rb') as f:
        response = requests.request(
            upload_method.upper(),
            upload_url,
            headers=upload_headers,
            data=f,
            timeout=120
        )
        response.raise_for_status()


def finish_upload(file_id: str) -> None:
    """完成上传流程"""
    if not BYTEHOUSE_HOST:
        print("Error: Please set BYTEHOUSE_HOST environment variable", file=sys.stderr)
        sys.exit(1)
    
    url = build_kb_api_url(BYTEHOUSE_HOST, 'knowledge-base/file/complete-upload')
    headers = get_auth_headers()
    
    payload = {
        "fileID": file_id
    }
    
    response = requests.post(url, headers=headers, json=payload, timeout=30)
    response.raise_for_status()


def load_file(
    file_id: str,
    chunk_size: int = 512,
    delimiters: list = None,
    enable_image_ocr: bool = False,
    enable_chunk_auto_merge: bool = False
) -> None:
    """加载文件到知识库，启动切片处理"""
    if delimiters is None:
        delimiters = ["#", "##"]
    
    if not BYTEHOUSE_HOST:
        print("Error: Please set BYTEHOUSE_HOST environment variable", file=sys.stderr)
        sys.exit(1)
    
    url = build_kb_api_url(BYTEHOUSE_HOST, 'knowledge-base/file/load')
    headers = get_auth_headers()
    
    # 构建切片配置
    chunk_settings = {
        "size": chunk_size,
        "delimiters": delimiters
    }
    
    if enable_image_ocr:
        chunk_settings["enableImageOcr"] = True
    
    if enable_chunk_auto_merge:
        chunk_settings["enableChunkAutoMerge"] = True
    
    payload = {
        "fileID": file_id,
        "chunkSettings": chunk_settings
    }

    from create_knowledge_base import get_claw_id
    if claw_id := get_claw_id():
        payload["tags"] = [{"key": "claw_id", "value": claw_id}]
    
    response = requests.post(url, headers=headers, json=payload, timeout=30)
    response.raise_for_status()


def main():
    """命令行入口"""
    parser = argparse.ArgumentParser(
        description='ByteHouse 知识库文件上传工具',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
示例:
  # 上传文件
  python3 upload_file_to_kb.py --kb-id 123 --file ./business_rules.pdf
  
  # 自定义切片配置
  python3 upload_file_to_kb.py --kb-id 123 --file ./document.md --chunk-size 1024 --delimiters "#,##,###"
  
  # 启用图片OCR和自动合并
  python3 upload_file_to_kb.py --kb-id 123 --file ./report.pdf --enable-image-ocr --enable-chunk-auto-merge

环境变量:
  BYTEHOUSE_HOST      - ByteHouse 主机 (如 tenant-xxx-cn-beijing-public.bytehouse.volces.com)
  BYTEHOUSE_PASSWORD  - 密码 (作为 Bearer token)
'''
    )
    
    parser.add_argument('--file', required=True, help='要上传的文件路径')
    parser.add_argument('--kb-id', type=int, required=True, help='指定知识库ID（必填）')
    parser.add_argument('--chunk-size', type=int, default=512, help='切片大小（字节），默认512')
    parser.add_argument('--delimiters', type=str, default='#,##', help='切片分隔符，逗号分隔，默认"#,##"')
    parser.add_argument('--enable-image-ocr', action='store_true', help='启用图片OCR识别，默认关闭')
    parser.add_argument('--enable-chunk-auto-merge', action='store_true', help='启用切片自动合并，默认关闭')
    
    args = parser.parse_args()
    
    # 检查文件是否存在
    if not os.path.isfile(args.file):
        print(f"Error: File not found: {args.file}", file=sys.stderr)
        sys.exit(1)
    
    try:
        # 获取知识库ID
        kb_id = args.kb_id
        
        # 获取文件信息
        file_name = os.path.basename(args.file)
        file_size = os.path.getsize(args.file)
        
        print("=========================================")
        print("ByteHouse 知识库文件上传")
        print("=========================================")
        print(f"知识库ID: {kb_id}")
        print(f"文件: {args.file}")
        print(f"文件名: {file_name}")
        print(f"文件大小: {file_size / 1024:.2f} KB")
        print()
        
        # Step 1: 生成上传URL
        print("Step 1/4: 生成预签名上传URL...")
        file_id, upload_url, upload_method, upload_headers = generate_upload_url(kb_id, file_name, file_size)
        print(f"  ✅ 成功，文件ID: {file_id}")
        print(f"  上传URL: {upload_url}")
        print(f"  上传方法: {upload_method}")
        
        # Step 2: 上传文件
        print("\nStep 2/4: 上传文件到对象存储...")
        upload_file(upload_url, upload_method, upload_headers, args.file)
        print("  ✅ 文件上传成功")
        
        # Step 3: 完成上传
        print("\nStep 3/4: 完成上传流程...")
        finish_upload(file_id)
        print("  ✅ 上传流程完成")
        
        # Step 4: 加载文件到知识库
        print("\nStep 4/4: 加载文件到知识库（启动切片处理）...")
        delimiters = [d.strip() for d in args.delimiters.split(',')]
        load_file(
            file_id, 
            args.chunk_size, 
            delimiters, 
            args.enable_image_ocr, 
            args.enable_chunk_auto_merge
        )
        print("  ✅ 文件加载成功，切片处理已启动")
        
        print("\n=========================================")
        print("✅ 所有步骤完成！文件已成功上传到知识库")
        print("=========================================")
        
    except Exception as e:
        print(f"\n❌ 上传失败: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()