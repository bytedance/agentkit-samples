# -*- coding: utf-8 -*-
# 大模型安全测评全流程管理技能配置文件

# API鉴权信息
username = "xxxxxx"
password = "xxxxxxx"
host = "https://xxxxx:31171"
api_prefix = "/api/top/wuji/cn-north-1/2025-01-01"

# 缓存有效期（秒），设置为0表示禁用缓存
# 默认缓存时间（用于未单独配置的缓存）
cache_ttl = 3600

# 各类资源的缓存有效期（秒），优先级高于 cache_ttl
cache_ttl_token = 7200        # Token缓存
cache_ttl_suite = 0        # 测评集缓存
cache_ttl_asset = 0        # 模型资产缓存
cache_ttl_agent = 0        # 智能体资产缓存
cache_ttl_openclaw = 0      # OpenClaw资产缓存
cache_ttl_scenario = 3600       # 安全测评剧本缓存

# 数据存储目录（相对于技能根目录）
data_dir = "data"
