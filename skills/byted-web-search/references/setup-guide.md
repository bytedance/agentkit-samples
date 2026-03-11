# Byted Web Search — 服务开通与凭证申请指南

本文档帮助从零开始申请和配置 Byted Web Search 依赖的火山引擎联网搜索 API 服务。

## 概览

```
注册账号 → 开通服务 → 获取凭证 → 配置环境变量 → 调用 API
  (1次)      (1次)      (1次)        (1次)        (随时)
```

整个流程约 5~10 分钟。

---

## 第一步：注册火山引擎账号

> 已有账号可跳过。

1. 访问 https://www.volcengine.com
2. 点击右上角【注册】
3. 使用手机号注册（也支持飞书、抖音等第三方账号）
4. 首次登录控制台需完成**实名认证**

---

## 第二步：开通融合信息搜索服务

融合信息搜索 API 属于「联网问答 Agent」产品的一部分，需要先在控制台开通。

### 2.1 进入控制台

访问：https://console.volcengine.com/ask-echo

### 2.2 正式开通

左侧栏找到"融合信息搜索"-"web信息搜索"：
1. 点击【正式开通】

### 2.5 计费参考

| 服务 | 计费方式 | 价格 |
|------|---------|------|
| 融合信息搜索 - web 搜索 | 按次 | 约 0.03 元/次 |

详细计费：https://www.volcengine.com/docs/85508/1510784

---

## 第三步：获取凭证

支持两种凭证方式，**二选一**。

### 方式 A：API Key（推荐）

API Key 是最简单的接入方式，无需签名计算。

1. 打开 [融合信息搜索 APIKey 管理页](https://console.volcengine.com/ask-echo/web-search)
2. 点击页面顶部的【融合信息搜索】页签
3. 点击【创建 API Key】按钮
4. 在弹窗中填写 API Key 名称（如 "my-search-key"），点击【创建】
5. **复制生成的 API Key 并妥善保存**

使用方式：在请求 Header 中设置 `Authorization: Bearer <your_api_key>`

对应的 API 地址：`https://open.feedcoopapi.com/search_api/web_search`

### 方式 B：AK/SK（适合已有火山引擎生态的用户）

AK/SK 使用 HMAC-SHA256 签名鉴权，适合与其他火山引擎服务统一管理凭证。

1. 登录 [火山引擎控制台](https://console.volcengine.com/)
2. 点击右上角**头像** → 选择「**API 访问密钥**」
3. 点击【**创建密钥**】
4. 系统生成一对密钥：
    - **Access Key ID**（AK）：公开标识符
    - **Secret Access Key**（SK）：私密密钥
5. **立即复制并保存 SK**（仅创建时显示一次，之后无法再查看）

> 安全建议：不要使用主账号密钥，建议创建 IAM 子用户并授权。

对应的 API 地址：`https://mercury.volcengineapi.com?Action=WebSearch&Version=2025-01-01`

详细文档：https://www.volcengine.com/docs/6291/65568

### 子账号权限配置

如果使用 IAM 子用户的 AK/SK，需要主账号授权：

1. 主账号登录控制台
2. 点击头像 → 进入「访问控制」模块
3. 在「用户」页面找到子账号，点击【管理】
4. 切换到【权限】标签页
5. 点击【添加权限】
6. 搜索 `TorchlightApiFullAccess`，选中后确认
7. 如需控制台访问，还需添加 `ContentCustomFullAccess` 权限

---

## 第四步：配置环境变量

根据你选择的凭证方式，设置对应环境变量：

### API Key 方式

```bash
export WEB_SEARCH_API_KEY="your_api_key_here"
```

### AK/SK 方式

```bash
export VOLCENGINE_ACCESS_KEY="your_access_key_id"
export VOLCENGINE_SECRET_KEY="your_secret_access_key"
```

建议将环境变量写入 `~/.bashrc` 或 `~/.zshrc` 以持久化。

---

## 第五步：验证调用

```bash
python scripts/web_search.py "北京今日天气"
```

如果看到搜索结果输出，说明配置成功。

---

## 常见问题

### Q: Secret Access Key 忘了怎么办？
A: SK 仅创建时显示一次，无法找回。需删除旧密钥，重新创建。

### Q: API 调用返回权限错误？
A: 检查：(1) 服务是否已开通（Lite 版需正式开通）；(2) 子账号是否已授权 `TorchlightApiFullAccess`。

### Q: 免费额度用完了怎么办？
A: 点击【正式开通】完成支付后可继续使用。

### Q: 欠费后服务会立即停吗？
A: 不会立即停。后付费模式：欠费通知后 24 小时内充值可恢复；包年订阅：到期通知后 12 小时内续费可恢复。

### Q: 收到403错误码怎么办？
A: 一般是请求无权限或账号欠费导致的，可以登录火山控制台检查开通状态和账户信息。

---

## 相关链接速查

| 用途 | 链接 |
|------|------|
| 注册账号 | https://www.volcengine.com |
| 联网问答 Agent 控制台 | https://console.volcengine.com/ask-echo |
| 融合信息搜索 API Key 管理 | https://console.volcengine.com/ask-echo/web-search |
| AK/SK 密钥管理 | 控制台右上角头像 → API 访问密钥 |
| AK/SK 文档 | https://www.volcengine.com/docs/6291/65568 |
| 签名方法文档 | https://www.volcengine.com/docs/6369/67269 |
| 融合信息搜索 API 文档 | https://www.volcengine.com/docs/85508/1650263 |
| 产品计费 | https://www.volcengine.com/docs/85508/1510784 |
| 快速入门 | https://www.volcengine.com/docs/85508/1544858 |
| 操作指南 | https://www.volcengine.com/docs/85508/1512748 |
