#!/usr/bin/env python3
import sys
import json
import requests
from urllib.parse import urlparse

API_BASE = "https://docs-api.cn-beijing.volces.com/api/v1/doc"
REQUEST_TIMEOUT = 15  # 超时时间15秒，防止永久阻塞

# 已取消负向关键词判断逻辑，所有查询默认放行

def search(query, limit=10, service_codes=None):
    """检索火山引擎文档"""
    url = f"{API_BASE}/search"
    payload = {
        "Query": query,
        "Limit": limit
    }
    if service_codes:
        payload["ServiceCodes"] = service_codes
    
    headers = {
        "Content-Type": "application/json"
    }
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        return {"error": f"检索请求失败: {str(e)}"}

def fetch(doc_url):
    """获取文档完整内容，自动处理URL中的query参数"""
    parsed = urlparse(doc_url)
    # 完全剥离query参数和fragment参数，确保URL纯净
    clean_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
    
    url = f"{API_BASE}/fetch"
    payload = {
        "Url": clean_url
    }
    headers = {
        "Content-Type": "application/json"
    }
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        result = response.json()
        # 始终返回纯净URL
        if "Result" in result:
            result["Result"]["CleanUrl"] = clean_url
        return result
    except Exception as e:
        return {"error": f"内容获取请求失败: {str(e)}"}

def print_help():
    help_info = {
        "name": "volcengine-docs 火山引擎文档查询工具",
        "usage": [
            {
                "action": "search",
                "desc": "检索火山引擎文档",
                "params": "<查询关键词> [返回数量] [产品编码1,产品编码2...]",
                "example": 'python seedance-docs.py search "tos是什么" 1 tos'
            },
            {
                "action": "fetch",
                "desc": "获取文档完整内容",
                "params": "<火山引擎文档链接>",
                "example": 'python seedance-docs.py fetch "https://www.volcengine.com/docs/6349/162514?lang=zh"'
            }
        ]
    }
    print(json.dumps(help_info, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print_help()
        sys.exit(1)
    
    action = sys.argv[1]
    result = {}
    
    if action == "search":
        if len(sys.argv) < 3:
            result = {"error": "缺少查询关键词", "help": "用法: python seedance-docs.py search <查询关键词> [返回数量] [产品编码1,产品编码2...]"}
        else:
            query = sys.argv[2]
            limit = 10
            service_codes = None
            if len(sys.argv) >=4:
                try:
                    limit = int(sys.argv[3])
                except ValueError:
                    result = {"error": "返回数量必须是数字"}
            if len(sys.argv) >=5:
                service_codes = sys.argv[4].split(",")
            
            if "error" not in result:
                result = search(query, limit, service_codes)
    
    elif action == "fetch":
        if len(sys.argv) < 3:
            result = {"error": "缺少文档URL", "help": "用法: python seedance-docs.py fetch <火山引擎文档链接>"}
        else:
            doc_url = sys.argv[2]
            result = fetch(doc_url)
    
    else:
        result = {"error": f"未知操作 {action}", "help": "支持的操作: search, fetch"}
    
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if "error" in result:
        sys.exit(1)
