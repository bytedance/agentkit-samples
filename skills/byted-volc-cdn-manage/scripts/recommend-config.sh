#!/bin/bash

# 火山引擎 CDN 推荐配置逻辑
# 此文件被其他脚本引用，生成基于业务类型的推荐配置

# 根据业务类型生成推荐配置
# 参数: $1 - 业务类型 (web/download/video)
# 输出: JSON 格式的推荐配置字符串
get_recommend_config() {
    local SERVICE_TYPE="$1"
    
    if [ "$SERVICE_TYPE" = "video" ]; then
        cat <<EOF
  "Cache": [
    {
      "CacheAction": {
        "Action": "cache",
        "IgnoreCase": false,
        "Ttl": 0,
        "DefaultPolicy": "no_cache"
      },
      "Condition": {
        "ConditionRule": [
          {
            "Object": "filetype",
            "Operator": "match",
            "Type": "url",
            "Value": "php;jsp;asp;aspx"
          }
        ]
      }
    },
    {
      "CacheAction": {
        "Action": "cache",
        "IgnoreCase": false,
        "Ttl": 2592000,
        "DefaultPolicy": "default"
      },
      "Condition": {
        "ConditionRule": [
          {
            "Object": "path",
            "Operator": "match",
            "Type": "url",
            "Value": "/*"
          }
        ]
      }
    }
  ],
  "Range": {
    "Switch": true,
    "RangeSize": 1,
    "Unit": "MB"
  },
  "MultiRange": {
    "Switch": true
  },
  "CacheKey": [
    {
      "CacheKeyAction": {
        "CacheKeyComponents": [
          {
            "Action": "exclude",
            "IgnoreCase": false,
            "Object": "queryString",
            "Subobject": "*"
          }
        ]
      },
      "Condition": {
        "ConditionRule": [
          {
            "Object": "path",
            "Operator": "match",
            "Type": "url",
            "Value": "/*"
          }
        ]
      }
    },
    {
      "CacheKeyAction": {
        "CacheKeyComponents": [
          {
            "Action": "include",
            "IgnoreCase": true,
            "Object": "queryString",
            "Subobject": "*"
          }
        ]
      },
      "Condition": {
        "ConditionRule": [
          {
            "Name": "",
            "Object": "directory",
            "Operator": "match",
            "Type": "url",
            "Value": "/"
          }
        ]
      }
    }
  ],
  "FollowRedirect": true,
  "VideoDrag": {
    "Switch": true
  }
EOF
    elif [ "$SERVICE_TYPE" = "web" ]; then
        cat <<EOF
  "Cache": [
    {
      "CacheAction": {
        "Action": "cache",
        "IgnoreCase": false,
        "Ttl": 0,
        "DefaultPolicy": "no_cache"
      },
      "Condition": {
        "ConditionRule": [
          {
            "Object": "filetype",
            "Operator": "match",
            "Type": "url",
            "Value": "php;jsp;asp;aspx"
          }
        ]
      }
    },
    {
      "CacheAction": {
        "Action": "cache",
        "IgnoreCase": false,
        "Ttl": 2592000,
        "DefaultPolicy": "default"
      },
      "Condition": {
        "ConditionRule": [
          {
            "Object": "path",
            "Operator": "match",
            "Type": "url",
            "Value": "/*"
          }
        ]
      }
    }
  ],
  "Compression": {
    "Switch": true,
    "CompressionRules": [
      {
        "CompressionAction": {
          "CompressionType": ["gzip"],
          "CompressionFormat": "default",
          "CompressionTarget": "*",
          "MinFileSizeKB": 0
        }
      }
    ]
  },
  "PageOptimization": {
    "PageOptimizationAction": "on"
  }
EOF
    elif [ "$SERVICE_TYPE" = "download" ]; then
        cat <<EOF
  "Cache": [
    {
      "CacheAction": {
        "Action": "cache",
        "IgnoreCase": false,
        "Ttl": 0,
        "DefaultPolicy": "no_cache"
      },
      "Condition": {
        "ConditionRule": [
          {
            "Object": "filetype",
            "Operator": "match",
            "Type": "url",
            "Value": "php;jsp;asp;aspx"
          }
        ]
      }
    },
    {
      "CacheAction": {
        "Action": "cache",
        "IgnoreCase": false,
        "Ttl": 2592000,
        "DefaultPolicy": "default"
      },
      "Condition": {
        "ConditionRule": [
          {
            "Object": "path",
            "Operator": "match",
            "Type": "url",
            "Value": "/*"
          }
        ]
      }
    }
  ],
  "Range": {
    "Switch": true,
    "RangeSize": 1,
    "Unit": "MB"
  },
  "MultiRange": {
    "Switch": true
  },
  "CacheKey": [
    {
      "CacheKeyAction": {
        "CacheKeyComponents": [
          {
            "Action": "exclude",
            "IgnoreCase": false,
            "Object": "queryString",
            "Subobject": "*"
          }
        ]
      },
      "Condition": {
        "ConditionRule": [
          {
            "Object": "path",
            "Operator": "match",
            "Type": "url",
            "Value": "/*"
          }
        ]
      }
    },
    {
      "CacheKeyAction": {
        "CacheKeyComponents": [
          {
            "Action": "include",
            "IgnoreCase": true,
            "Object": "queryString",
            "Subobject": "*"
          }
        ]
      },
      "Condition": {
        "ConditionRule": [
          {
            "Name": "",
            "Object": "directory",
            "Operator": "match",
            "Type": "url",
            "Value": "/"
          }
        ]
      }
    }
  ],
  "FollowRedirect": true
EOF
    fi
}

# 根据业务类型获取推荐配置的说明
# 参数: $1 - 业务类型 (web/download/video)
get_recommend_config_desc() {
    local SERVICE_TYPE="$1"
    
    if [ "$SERVICE_TYPE" = "video" ]; then
        cat <<EOF
  📺 视频点播场景优化:
  ✓ 缓存规则: 所有文件 30 天, 动态文件不缓存
  ✓ Range 回源: 已启用 (1MB 分片)
  ✓ MultiRange: 已启用
  ✓ 缓存键: 忽略所有查询参数
  ✓ 302 跟随: 已启用
  ✓ 视频拖拽: 已启用
EOF
    elif [ "$SERVICE_TYPE" = "web" ]; then
        cat <<EOF
  🌐 网页加速场景优化:
  ✓ 缓存规则: 所有文件 30 天, 动态文件不缓存
  ✓ 智能压缩: 已启用 (仅 gzip, 默认格式)
  ✓ 页面优化: 已启用
EOF
    elif [ "$SERVICE_TYPE" = "download" ]; then
        cat <<EOF
  ⬇️  下载加速场景优化:
  ✓ 缓存规则: 所有文件 30 天, 动态文件不缓存
  ✓ Range 回源: 已启用 (1MB 分片)
  ✓ MultiRange: 已启用
  ✓ 缓存键: 忽略所有查询参数
  ✓ 302 跟随: 已启用
EOF
    fi
}
