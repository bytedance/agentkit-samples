# 🕵️‍♂️ Critic Agent (毒舌影评人)

Critic Agent 是 AI Movie Studio 的质量把关人，负责对 Director Agent 生成的视觉素材进行严格的审计和评分。它模拟了一位挑剔的专业美术指导，确保每一帧画面都符合高标准。

## 🧠 核心能力

### 1. 多模态视觉评估 (LLM-as-a-Judge)
不同于传统的基于规则（如 OpenCV 模糊检测）的评估，Critic Agent 使用先进的多模态大模型 (**Doubao Vision Pro**) 来像人类一样“看”图。

**评估维度**：
- **Visual Quality (视觉质量)**: 构图是否平衡？光影是否自然？清晰度如何？
- **Content Alignment (内容一致性)**: 画面内容是否忠实还原了 Prompt 的描述？
- **Style Consistency (风格一致性)**: 是否符合赛博朋克/皮克斯/水墨等预设风格？

### 2. 量化评分与反馈
Critic Agent 会输出结构化的 JSON 报告：
```json
{
    "evaluation": {
        "scores": [85, 90, 80], // [视觉, 内容, 风格]
        "reason": "构图极具张力，赛博朋克的霓虹质感还原得很到位。但在背景细节上略显杂乱，建议简化背景元素。"
    }
}
```
只有当平均分超过 **75分** 且无单项低于 **50分** 时，素材才会被标记为 `Approved`。

---

## 🔗 交互流程

Critic Agent 在系统中处于 "Review" 环节，与 Director Agent 紧密配合：

1.  **Input (输入)**: 接收包含 `MediaItem` 列表的 `Shot` 对象。
    - **关键点**: Director 生成的图片/视频会自动上传至 TOS，Critic 接收到的是 **HTTP URL**，而非本地文件或 Base64。
2.  **Process (处理)**: 调用 `evaluate_shots` 工具，将 URL 发送给 Doubao Vision 模型进行并发评估。
3.  **Output (输出)**: 返回带有 `score` 和 `feedback` 的 `ReviewOutput`。
    - 如果 `is_approved=False`，Producer 会将 `feedback` 反馈给 Director 进行重绘。

---

## 🛠️ 工具链

### `evaluate_shots`
- **类型**: `google.adk.tools.BaseTool`
- **实现**: `agents/critic/tools.py`
- **模型**: `doubao-1-5-vision-pro-32k-250115`
- **并发**: 使用 `asyncio` 实现高并发评估，大幅降低等待时间。

---

## 🚀 部署指南

### 环境变量
请确保 `agentkit.yaml` 或运行时环境中配置了以下变量：
- `MODEL_AGENT_API_KEY`: 火山引擎 Ark API Key (用于调用 Doubao Vision)。
- `MODEL_EVALUATE_ITEM`: (可选) 指定评估模型，默认为 `doubao-1-5-vision-pro-32k-250115`。

### 注意事项
- **依赖轻量化**: 本 Agent 不依赖 `opencv` 或 `numpy` 等重型库，部署包体积小，启动速度快。
- **构建缓存**: 如需更新代码逻辑，请在部署前清理 `.agentkit` 目录或更新 `agentkit.yaml` 中的 `image_tag`。
