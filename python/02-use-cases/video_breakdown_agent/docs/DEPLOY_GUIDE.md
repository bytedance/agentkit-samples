# 部署指南

## 🚀 云端重新部署步骤

由于更新了 `requirements.txt`（添加了 `imageio-ffmpeg` 依赖），需要重新构建并部署应用。

### 1️⃣ 确认环境变量已配置

在 AgentKit 控制台确认以下环境变量已正确填写：

**必需变量**：
```bash
MODEL_AGENT_API_KEY=<您的豆包 API Key>
VOLCENGINE_ACCESS_KEY=<您的火山引擎 AK>
VOLCENGINE_SECRET_KEY=<您的火山引擎 SK>
DATABASE_TOS_BUCKET=video-breakdown-uploads
DATABASE_TOS_REGION=cn-beijing
```

### 2️⃣ 重新部署

在项目根目录执行：

```bash
# 确保在正确的目录
cd /Users/edy/Downloads/agentkit-samples-main/02-use-cases/video_breakdown_agent

# 激活虚拟环境（如果使用 conda）
source ~/.venv/bin/activate  # 或 conda activate video-breakdown-agent

# 重新部署到云端
agentkit launch
```

### 3️⃣ 等待构建完成

部署过程包括：
1. 📦 打包项目代码
2. 🔧 上传到 TOS
3. 🏗️ 云端构建 Docker 镜像（安装 imageio-ffmpeg）
4. 🚢 部署到 Runtime
5. ✅ 服务就绪

预计耗时：3-5 分钟

### 4️⃣ 验证部署

部署成功后，在控制台测试：

1. **基础对话测试**：
   ```
   你好，介绍一下你的功能
   ```

2. **视频分析测试**：
   ```
   帮我分析这个视频的分镜
   ```
   然后上传一个短视频文件（< 50MB）

如果配置正确，Agent 应该能够：
- ✅ 接收并处理视频文件
- ✅ 使用 FFmpeg 进行分镜拆解
- ✅ 返回完整的分析结果

---

## 🐛 常见问题

### Q1: 部署时提示 CR 配额超限？

**解决方案**：使用已有的 CR 实例

```bash
agentkit config --cr_instance_name nodesk-center
agentkit launch
```

### Q2: 运行时报错"FFmpeg 缺失"？

**原因**：旧版本的镜像没有包含 `imageio-ffmpeg`

**解决方案**：重新部署（按照上述步骤）

### Q3: 视频分析失败，提示 TOS 权限错误？

**原因**：环境变量 `VOLCENGINE_ACCESS_KEY` 或 `VOLCENGINE_SECRET_KEY` 未配置或错误

**解决方案**：
1. 在控制台检查环境变量配置
2. 重启 Runtime 使配置生效

### Q4: ASR 语音识别不工作？

**说明**：ASR 是可选功能，未配置时会跳过语音识别，不影响视频分析

**解决方案**（如需启用）：
```bash
# 在控制台添加环境变量
ASR_APP_ID=<您的 ASR App ID>
ASR_ACCESS_KEY=<您的 ASR Access Key>
```

---

## 📊 部署后检查清单

- [ ] Runtime 状态为 "运行中"
- [ ] 环境变量已配置（至少 3 个必需变量）
- [ ] 能够进行基础对话
- [ ] 能够上传视频文件
- [ ] 视频分析功能正常
- [ ] TOS 存储桶可访问

---

## 🔗 相关链接

- AgentKit 控制台：https://console.volcengine.com/agentkit
- TOS 存储桶管理：https://console.volcengine.com/tos/bucket
- 火山方舟 API Key：https://console.volcengine.com/ark/region:ark+cn-beijing/apiKey
- IAM 密钥管理：https://console.volcengine.com/iam/keymanage/

---

## 💬 获取帮助

如遇到问题，请提供：
1. Runtime ID 或名称
2. 错误信息截图
3. 环境变量配置（脱敏后）
4. 部署日志
