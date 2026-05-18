
# 参数说明

本文档详细介绍火山引擎 CDN 域名创建的所有参数。

---

## 基础参数

| 参数 | 类型 | 必填 | 说明 | 示例 |
|------|------|------|------|------|
| `Domain` | String | ✅ | 要添加的加速域名 | `www.example.com` |
| `ServiceType` | String | ✅ | 业务类型：&lt;br&gt;- `web`（网页）&lt;br&gt;- `download`（下载）&lt;br&gt;- `video`（点播） | `download` |
| `Origin` | Array | ✅ | 源站配置，详见下方 | - |
| `ServiceRegion` | String | - | 加速区域：&lt;br&gt;- `chinese_mainland`（中国内地，默认）&lt;br&gt;- `global`（全球）&lt;br&gt;- `outside_chinese_mainland`（全球不含内地） | `chinese_mainland` |
| `Project` | String | - | 项目名称，默认 `default` | `default` |
| `OriginProtocol` | String | - | 回源请求使用的协议：&lt;br&gt;- `http`（默认）&lt;br&gt;- `https`&lt;br&gt;- `followclient`（与用户请求相同） | `http` |
| `OriginHost` | String | - | 回源请求访问的站点域名，默认与 `Domain` 相同。如果源站是对象存储桶，默认值与源站 `Address` 相同 | `img.example.com` |

---

## 源站配置（Origin）

```json
{
  "OriginAction": {
    "OriginLines": [
      {
        "Address": "1.1.1.1",
        "InstanceType": "ip",
        "OriginType": "primary",
        "HttpPort": "80",
        "HttpsPort": "443",
        "Weight": "100"
      }
    ]
  }
}
```

### OriginAction.OriginLines 参数说明

| 参数 | 类型 | 必填 | 说明 | 可选值 |
|------|------|------|------|--------|
| `Address` | String | ✅ | 源站地址，根据 `InstanceType` 不同有不同说明：&lt;br&gt;- `ip`：IPv4 或 IPv6 地址&lt;br&gt;- `domain`：源站域名（不能是泛域名）&lt;br&gt;- `tos`：对象存储桶域名（阿里云 OSS、腾讯云 COS、AWS S3 等） | `1.1.1.1` |
| `InstanceType` | String | ✅ | 源站类型 | `ip`、`domain`、`tos` |
| `OriginType` | String | ✅ | 源站类别：&lt;br&gt;- `primary`（主源站，至少需要一个）&lt;br&gt;- `backup`（备源站，可选） | `primary` |
| `HttpPort` | String | - | HTTP 回源端口，取值范围 1-65535，默认 `80`。仅当 `InstanceType` 为 `ip` 或 `domain` 时有效 | `80` |
| `HttpsPort` | String | - | HTTPS 回源端口，取值范围 1-65535，默认 `443`。仅当 `InstanceType` 为 `ip` 或 `domain` 时有效 | `443` |
| `Weight` | String | - | 源站权重，取值范围 1-100，默认 `1`。权重越大，被选择概率越大 | `100` |
| `OriginHost` | String | - | 回源站点域名，适用于源站服务器有多个站点的情况。优先级高于全局 `OriginHost`，默认与全局 `OriginHost` 相同 | `img.example.com` |
| `PrivateBucketAccess` | Boolean | - | 存储桶是否是私有桶，仅当 `InstanceType` 为 `tos` 时有效，默认 `false` | `false` |
| `PrivateBucketAuth` | Object | - | 访问存储桶的凭据，当 `PrivateBucketAccess` 为 `true` 时必填 | - |

### PrivateBucketAuth 参数说明

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `Switch` | Boolean | ✅ | 必须为 `true` |
| `TosAuthInformation` | Object | - | 存储桶访问凭证 |
| `AuthType` | String | - | 鉴权方式：&lt;br&gt;- `tos`（火山引擎 TOS）&lt;br&gt;- `cos`（腾讯云 COS）&lt;br&gt;- `oss`（阿里云 OSS）&lt;br&gt;- `aws_common`（AWS S3 和 S3 兼容） |

### TosAuthInformation 参数说明

| 参数 | 类型 | 说明 |
|------|------|------|
| `AccessKeyId` | String | AccessKey ID（腾讯云称为 SecretId），长度 5-100 字符 |
| `AccessKeySecret` | String | AccessKey Secret（腾讯云称为 SecretKey），长度 5-100 字符 |
| `Region` | String | 当 `AuthType` 为 `aws_common` 且 `PrivateBucketAccess` 为 `true` 时必填，表示存储桶 region code |

---

## 推荐配置规则

本项目根据业务类型自动应用推荐配置规则，详细参数说明如下：

### 点播场景（video）

```json
{
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
}
```

### 网页场景（web）

```json
{
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
}
```

### 下载场景（download）

```json
{
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
}
```

---

## 缓存规则（Cache）

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `Cache` | Array | - | 缓存规则数组，最多 50 条 |
| `Cache[].CacheAction` | Object | ✅ | 缓存行为配置 |
| `Cache[].CacheAction.Action` | String | ✅ | 固定值 `cache` |
| `Cache[].CacheAction.IgnoreCase` | Boolean | - | 是否大小写不敏感，默认 `false` |
| `Cache[].CacheAction.Ttl` | Integer | ✅ | 缓存时长（秒），0-315360000。0 表示不缓存/立即过期 |
| `Cache[].CacheAction.DefaultPolicy` | String | - | 缓存策略：`force_cache`、`default`、`origin_first`、`origin_first_Replenish`、`no_cache`，默认 `default` |
| `Cache[].Condition` | Object | ✅ | 匹配条件 |
| `Cache[].Condition.ConditionRule` | Array | ✅ | 匹配规则数组，最多 1 条 |
| `Cache[].Condition.ConditionRule[].Object` | String | ✅ | 匹配对象：`filetype`、`directory`、`path`、`regex` |
| `Cache[].Condition.ConditionRule[].Operator` | String | ✅ | 固定值 `match` |
| `Cache[].Condition.ConditionRule[].Type` | String | ✅ | 固定值 `url` |
| `Cache[].Condition.ConditionRule[].Value` | String | ✅ | 匹配值，格式随 Object 变化 |

---

## 分片回源（Range）

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `Range` | Object | - | 分片回源配置，优先级高于 OriginRange |
| `Range.Switch` | Boolean | - | 是否启用分片回源，默认 `false` |
| `Range.RangeSize` | Integer | - | 分片大小：Unit=MB 时 1-40，Unit=KB 时只能填 512，默认 1 |
| `Range.Unit` | String | - | 分片大小单位：`KB`、`MB`，默认 `MB` |

---

## 多重范围（MultiRange）

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `MultiRange` | Object | - | Multi-range 配置 |
| `MultiRange.Switch` | Boolean | - | 是否允许多重 Range 请求，默认 `false` |

---

## 缓存键（CacheKey）

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `CacheKey` | Array | - | 缓存键规则数组，最多 50 条，最后一条必须是强制默认规则 |
| `CacheKey[].CacheKeyAction` | Object | ✅ | 缓存键行为配置 |
| `CacheKey[].CacheKeyAction.CacheKeyComponents` | Array | ✅ | 缓存键组件数组 |
| `CacheKey[].CacheKeyAction.CacheKeyComponents[].Action` | String | ✅ | 行为类型：`include`、`exclude`、`includePart`、`excludePart` |
| `CacheKey[].CacheKeyAction.CacheKeyComponents[].IgnoreCase` | Boolean | - | 是否大小写不敏感，默认 `false`（仅 includePart/excludePart 有效） |
| `CacheKey[].CacheKeyAction.CacheKeyComponents[].Object` | String | ✅ | 固定值 `queryString` |
| `CacheKey[].CacheKeyAction.CacheKeyComponents[].Subobject` | String | ✅ | include/exclude 时固定为 `*`，includePart/excludePart 时为参数名，多个用 `;` 分隔 |
| `CacheKey[].Condition` | Object | ✅ | 匹配条件（结构同 Cache） |

---

## 回源重定向跟随（FollowRedirect）

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `FollowRedirect` | Boolean | - | 是否跟随回源 3xx 重定向，默认 `false` |

---

## 视频拖拽（VideoDrag）

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `VideoDrag` | Object | - | 视频拖拽配置 |
| `VideoDrag.Switch` | Boolean | ✅ | 是否启用视频拖拽 |

---

## 智能压缩（Compression）

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `Compression` | Object | - | 智能压缩配置 |
| `Compression.Switch` | Boolean | ✅ | 是否启用智能压缩 |
| `Compression.CompressionRules` | Array | - | 压缩规则数组 |
| `Compression.CompressionRules[].CompressionAction` | Object | ✅ | 压缩行为配置 |
| `Compression.CompressionRules[].CompressionAction.CompressionType` | Array | ✅ | 压缩算法：`gzip`、`br`，可同时指定 |
| `Compression.CompressionRules[].CompressionAction.CompressionFormat` | String | - | 压缩格式：`default`（内置列表）、`customize`（自定义）、`all`（全部），指定后 Condition 必须为 null |
| `Compression.CompressionRules[].CompressionAction.CompressionTarget` | String | - | CompressionFormat 为 `default`/`all` 时固定为 `*`，为 `customize` 时填 MIME 类型，逗号分隔 |
| `Compression.CompressionRules[].CompressionAction.MinFileSizeKB` | Integer | - | 最小压缩文件大小（KB），0-2147483647，默认 0 |
| `Compression.CompressionRules[].CompressionAction.MaxFileSizeKB` | Integer | - | 最大压缩文件大小（KB），0-2147483647，不填表示无上限 |
| `Compression.CompressionRules[].Condition` | Object | - | 匹配条件（结构同 Cache，不支持 regex），与 CompressionFormat 互斥 |

---

## CompressionFormat=default 内置 Content-Type 列表

```
text/html、text/xml、text/plain、text/css、application/javascript、application/x-javascript、application/rss+xml、text/javascript、image/tiff、image/svg+xml、application/json、application/xml、text/plain; charset=utf-8
```


