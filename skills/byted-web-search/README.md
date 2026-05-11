# byted-web-search v1.3.4

火山引擎联网搜索 API Skill，适用于 Claw / OpenClaw Agent。

## 目录结构

```
byted-web-search/
├── SKILL.md                  # Agent 运行时指令（主文件）
├── references/
│   ├── setup-guide.md        # 开通与配置详细步骤
│   └── docs-index.md         # 官方文档 & 控制台链接索引
├── scripts/
│   └── web_search.py         # 搜索脚本（未修改）
├── LICENSE                   # Apache 2.0
└── README.md                 # 本文件
```

## 快速开始

1. 将本目录放入 Claw 技能目录
2. 获取 API Key：[联网搜索控制台](https://console.volcengine.com/search-infinity/api-key) 或 [Coding Plan 控制台](https://console.volcengine.com/ark/region:ark+cn-beijing/openManagement?LLM=%7B%7D&advancedActiveKey=subscribe&projectName=default)
3. 在聊天框直接发送 Key 给 Agent 即可

## v1.3.4 变更（基于 v1.3.3）

- **修正**：`--time-range` 支持自定义日期区间 `YYYY-MM-DD..YYYY-MM-DD`（脚本已支持，文档原缺失）
- **优化**：自然语言→参数映射示例增加时间区间场景
- **精简**：SKILL.md 与 references/ 去重，总上下文减少 26%
- **修正**：环境变量名统一为 `VOLCENGINE_ACCESS_KEY` / `VOLCENGINE_SECRET_KEY`
- **修正**：Key 来源提示统一为「其他来源 Key 不通用」
- **新增**：Coding Plan 控制台获取凭证路径
- **架构**：SKILL.md 为运行时指令，references/ 为补充参考文档，分离关注点

## 许可证

Apache License 2.0
