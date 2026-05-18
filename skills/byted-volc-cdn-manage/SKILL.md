---
name: byted-volc-cdn-manage
description: 通过火山引擎 CLI 管理 CDN 域名。支持新增域名和刷新预热, 使用时会先检查并安装 CLI（如需要）。
license: MIT
compatibility: Requires Volcengine CLI >= 1.0.39, access to Volcengine API
metadata:
  version: "2.0"
  author: ByteDance
---

# 火山引擎 CLI CDN 管理助手

本 Skill 帮助您通过火山引擎 CLI 管理 CDN 加速域名，包括新增域名、刷新和预热。

---

## 📋 功能说明

本 Skill 提供以下功能：

### 1. 新增域名
- 交互式配置
- 支持多种业务类型（web/download/video）
- 自动应用推荐配置
- 支持中国内地和全球加速

### 2. 刷新预热
- **刷新任务**：清除 CDN 节点上的缓存内容（支持文件刷新和目录刷新）
- **预热任务**：主动将源站内容预热到 CDN 节点

---

## 📋 智能流程（新增域名）

本 Skill 会自动执行以下流程：

**第一阶段：环境检查**
1. **检查 CLI 是否已安装**
2. **如果未安装**：引导您安装并配置火山引擎 CLI
3. **如果已安装**：检查 CLI 版本（需 >= 1.0.39）

**第二阶段：需求收集**
1. **检查必填项**：加速域名、区域、源站信息、业务类型
2. **使用默认值**：
   - 区域默认：`chinese_mainland`（中国内地）
   - 项目默认：`default`
3. **推荐配置**：根据业务类型自动应用推荐配置规则：
   - **web（网页加速）**：缓存规则、智能压缩、页面优化
   - **download（下载加速）**：缓存规则、分片回源、缓存键、302跟随
   - **video（视频点播）**：缓存规则、分片回源、缓存键、302跟随、视频拖拽
4. **询问用户**：必填项找不到默认值时，引导用户输入

**第三阶段：添加域名**
1. 收集完整信息后，执行 `ve cdn AddCdnDomain` 命令
2. 展示执行结果和后续步骤

---

## 📋 刷新预热流程

**提交预热任务**：
1. 选择预热操作
2. 输入要预热的 URL 列表
3. 确认并提交任务

**提交刷新任务**：
1. 选择刷新操作
2. 选择刷新类型（文件/目录）
3. 输入要刷新的 URL 列表
4. 确认并提交任务

---

## 🚀 快速开始

### 前置条件

1. **火山引擎 CLI 版本 &gt;= 1.0.39**（此版本及以上才支持 CDN 服务）
2. **已配置好 AK/SK 和 Region**

### 验证环境

```bash
# 检查 CLI 版本
ve version

# 查看当前配置
ve configure list
```

### 添加域名

#### 方式一：使用交互式脚本（推荐）

```bash
bash scripts/add-cdn-domain.sh
```

#### 方式二：使用快速脚本（命令行参数）

```bash
# 格式: bash scripts/add-domain-quick.sh <域名> <源站> [源站2] [源站3] [权重1] [权重2] [权重3] [业务类型] [服务区域]
# 业务类型: web / download / video
# 服务区域: chinese_mainland (默认) / global

# 示例：添加网页加速域名（中国内地）
bash scripts/add-domain-quick.sh www.example.com 1.1.1.1 "" "" 100 "" "" web chinese_mainland

# 示例：添加网页加速域名（全球）
bash scripts/add-domain-quick.sh www.example.com 1.1.1.1 "" "" 100 "" "" web global

# 示例：添加视频点播域名
bash scripts/add-domain-quick.sh video.example.com 1.1.1.1 "" "" 100 "" "" video
```

#### 方式三：直接使用命令（基础版）

```bash
BODY='{
  "Domain": "www.example.com",
  "Origin": [
    {
      "OriginAction": {
        "OriginLines": [
          {
            "Address": "1.1.1.1",
            "InstanceType": "ip",
            "OriginType": "primary"
          }
        ]
      }
    }
  ],
  "Project": "default",
  "ServiceRegion": "chinese_mainland",
  "ServiceType": "download"
}'

ve cdn AddCdnDomain --body "$BODY"
```

#### 方式四：使用推荐配置命令（推荐版）

**网页加速示例**：
```bash
BODY='{
  "Domain": "www.example.com",
  "Origin": [
    {
      "OriginAction": {
        "OriginLines": [
          {
            "Address": "1.1.1.1",
            "InstanceType": "ip",
            "OriginType": "primary"
          }
        ]
      }
    }
  ],
  "Project": "default",
  "ServiceRegion": "chinese_mainland",
  "ServiceType": "web",
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
}'

ve cdn AddCdnDomain --body "$BODY"
```

更多业务类型的推荐配置请参考 [参数说明](references/parameters.md)。

---

## 📚 详细文档

| 文档 | 说明 |
|------|------|
| [参数说明](references/parameters.md) | 完整的 API 参数说明 |
| [使用场景示例](references/examples.md) | 9 个常见使用场景示例 |
| [常见问题](references/faq.md) | FAQ 常见问题解答 |
| [CLI 安装指南](references/install-guide.md) | 火山引擎 CLI 安装和配置指南 |

---

## ✅ 成功响应示例

```json
{
  "ResponseMetadata": {
    "Action": "AddCdnDomain",
    "Region": "cn-guangzhou",
    "RequestId": "20260415170258108D89026C070556E439",
    "Service": "cdn",
    "Version": "2021-03-01"
  },
  "Result": {
    "ResourceIds": [
      "www.example.com"
    ]
  }
}
```

---

## 🔄 刷新和预热

### 提交预热任务

#### 方式一：使用交互式脚本（推荐）

```bash
bash scripts/cdn-refresh-preload.sh
# 选择 1. 提交预热任务
```

#### 方式二：使用快速脚本

```bash
# 格式: bash scripts/submit-preload.sh <url1> <url2> ...

# 示例：预热多个URL
bash scripts/submit-preload.sh https://www.example.com/1.jpg https://www.example.com/2.jpg
```

#### 方式三：直接使用命令

```bash
BODY='{
  "UrlList": [
    "https://www.example.com/1.jpg",
    "https://www.example.com/2.jpg"
  ]
}'

ve cdn SubmitPreloadTask --body "$BODY"
```

### 提交刷新任务

#### 方式一：使用交互式脚本（推荐）

```bash
bash scripts/cdn-refresh-preload.sh
# 选择 2. 提交刷新任务
```

#### 方式二：使用快速脚本

```bash
# 格式: bash scripts/submit-refresh.sh [--type <file|directory>] <url1> <url2> ...

# 示例：刷新文件（默认）
bash scripts/submit-refresh.sh https://www.example.com/1.jpg https://www.example.com/2.jpg

# 示例：刷新目录
bash scripts/submit-refresh.sh --type directory https://www.example.com/path/
```

#### 方式三：直接使用命令

**刷新文件：**
```bash
BODY='{
  "Type": "file",
  "UrlList": [
    "https://www.example.com/1.jpg",
    "https://www.example.com/2.jpg"
  ]
}'

ve cdn SubmitRefreshTask --body "$BODY"
```

**刷新目录：**
```bash
BODY='{
  "Type": "directory",
  "UrlList": [
    "https://www.example.com/path/"
  ]
}'

ve cdn SubmitRefreshTask --body "$BODY"
```

---

## 📝 添加域名后的步骤

1. **等待生效**：创建成功后，域名状态会从「配置中」变为「正常运行」（通常需要 1-5 分钟）

2. **获取 CNAME**：
   ```bash
   # 可以通过控制台查看，或使用 CLI 查询
   ve cdn DescribeCdnConfig --Domain "www.example.com"
   ```

3. **配置 DNS**：在您的 DNS 服务商处将域名解析指向 CNAME

4. **验证访问**：等待 DNS 生效后，测试访问

---

## 🔗 相关文档

- [火山引擎 CLI 文档](https://github.com/volcengine/volcengine-cli)
- [CDN AddCdnDomain API 文档](https://www.volcengine.com/docs/6454/97340)
- [CDN SubmitRefreshTask API 文档](https://www.volcengine.com/docs/6454/97345)
- [CDN SubmitPreloadTask API 文档](https://www.volcengine.com/docs/6454/97346)
- [火山引擎 CDN 控制台](https://console.volcengine.com/cdn)

