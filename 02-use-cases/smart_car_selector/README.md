# AgentKit-小懂车 (Smart Car Selector)

**AgentKit-小懂车** 是一个基于 [AgentKit](https://github.com/bytedance/agentkit) 构建的“单体 Unified Agent”购车咨询示例：用一个 Agent 覆盖用户真实选车旅程——求推荐、参数对比、口碑避坑、价格/金融算账、预约试驾与导航、选中后生成海报提供情绪价值。

项目主线采用 **Single Agent + Tools/Skills**：在不引入多智能体编排复杂度的前提下，保留可复核的确定性交付（Excel 表、可视化图片、地图路线等）。

## ✨ 核心亮点

- **真实选车场景**：推荐 → 参数表 → 口碑 → 金融表 → 试驾导航 → 海报，一条链路走完。
- **可复核交付**：参数对比表、金融分析表均可下载，可复用公式并支持用户改参数重算。
- **事实核验优先**：涉及参数/政策/口碑等事实点时优先 `web_search` 交叉核验，避免拍脑袋。
- **交付执行能力（可选）**：如启用 `mcp_router` 可做门店/路线/导航；未启用时也会输出门店筛选方法与到店清单，保证体验可用。
- **情绪价值补全**：选中车型后可用 `image_generate` 生成可分享海报与文案。
- **趣味彩蛋**：用户纠结难以拍板时，用掷骰子做“玄学推荐”并给理性兜底问题。

## 📂 项目结构

```text
.
├── agent.py                    # 核心 Agent（Unified）
├── agentkit-agent.py           # A2A 服务入口
├── agentkit.yaml               # AgentKit 配置（已脱敏）
├── instruction.md              # 系统提示词（包含完整选车旅程）
├── utils.py                    # 工具辅助（上传/清理输出等）
├── requirements.txt
├── pyproject.toml
├── project.toml
├── ENV.md
├── img/
└── skills/

skills/
└── dice-roller/                # 掷骰子彩蛋 Skill
```

## 🚀 本地启动

```bash
python3 -m pip install -r requirements.txt
python3 agentkit-agent.py
python3 -c "import requests; print(requests.get('http://127.0.0.1:8000/ping', timeout=5).text)"
```

环境变量较多，详见 [ENV.md](ENV.md)（建议复制 `.env.example` 为 `.env` 并填写必要项；不要把真实密钥提交到仓库）。

## 🧩 架构图

![场景架构图](img/process_smart_car_selector.jpg)

![Technical Architecture](img/archtecture_smart_car_selector.jpg)

## 🧭 典型用户旅程（你可以这样体验）

1. **求推荐**：给出预算/城市/用车场景，获取 2-3 款候选与取舍建议。
2. **对比参数**：说“对比参数/出参数表”，拿到可下载 Excel 参数对比表。
3. **对比口碑**：说“这车通病/能买吗”，获取真实车主反馈与避坑点。
4. **对比价格**：说“落地价/月供/还款表”，拿到可下载金融分析 Excel（含可调参数）。
5. **预约试驾**：说“帮我找店/导航/预约试驾”，输出门店与路线，并附预约话术与到店清单。
6. **生成海报**：选中车型后说“做个海报/朋友圈文案”，生成可分享海报。

## 📦 标准文件

- README.md：中文说明。
- README_en.md：英文说明。
- requirements.txt：依赖列表（本地运行）。
- pyproject.toml：本地 Python 工具链/打包元数据（可选）。
- project.toml：应用元数据（用于应用广场/发布场景）。
- LICENSE：默认 Apache-2.0 协议。
