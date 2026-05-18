
# CLI 安装指南

本文档详细介绍如何安装和配置火山引擎 CLI。

---

## 前置条件

1. 火山引擎账号已开通 CDN 服务
2. 已获取 AccessKey（AK）和 SecretKey（SK）

---

## 1. 检查系统架构

```bash
uname -m
```

- `arm64`：Apple Silicon (M1/M2/M3)
- `x86_64`：Intel 芯片

---

## 2. 下载 CLI

### Apple Silicon (arm64)

```bash
curl -L -s https://github.com/volcengine/volcengine-cli/releases/download/v1.0.39/volcengine-cli_1.0.39_darwin_arm64.zip -o ve.zip
```

### Intel (x86_64)

```bash
curl -L -s https://github.com/volcengine/volcengine-cli/releases/download/v1.0.39/volcengine-cli_1.0.39_darwin_amd64.zip -o ve.zip
```

---

## 3. 解压和安装

```bash
unzip -q ve.zip
mkdir -p ~/.local/bin
mv ve ~/.local/bin/
```

---

## 4. 配置环境变量

如果还没有配置环境变量，执行：

```bash
echo 'export PATH="$HOME/.local/bin:$PATH"' &gt;&gt; ~/.zshrc
source ~/.zshrc
```

---

## 5. 配置访问凭证

```bash
ve configure set \
  --access-key &lt;您的AK&gt; \
  --secret-key &lt;您的SK&gt; \
  --region cn-guangzhou \
  --profile default
```

### 常用地域

- `cn-beijing` - 华北2（北京）
- `cn-shanghai` - 华东2（上海）
- `cn-guangzhou` - 华南1（广州）

---

## 6. 验证配置

```bash
ve version
ve configure list
```

---

## 7. 升级 CLI（如果需要）

如果 CLI 版本低于 1.0.39，请按以下步骤升级：

### Apple Silicon (arm64)

```bash
curl -L -s https://github.com/volcengine/volcengine-cli/releases/download/v1.0.39/volcengine-cli_1.0.39_darwin_arm64.zip -o ve.zip
unzip -q -o ve.zip
mv ve ~/.local/bin/
```

### Intel (x86_64)

```bash
curl -L -s https://github.com/volcengine/volcengine-cli/releases/download/v1.0.39/volcengine-cli_1.0.39_darwin_amd64.zip -o ve.zip
unzip -q -o ve.zip
mv ve ~/.local/bin/
```

---

## 验证 CLI 版本

```bash
ve version
```

确保版本 &gt;= 1.0.39（此版本及以上才支持 CDN 服务）。

