# byted-las-pdf-parse-doubao 自检清单（Skill Hub）

- SKILL.md 顶部包含 YAML frontmatter（name/description）
- 文档不包含任何真实密钥、Token、Cookie（只引用 `LAS_API_KEY` 环境变量名）
- 文档包含预估价格步骤，且 references/prices.md 提供单价信息
- 推荐流程为 submit + 短轮询 poll，不包含阻塞等待示例
- 批处理示例包含 tos-ls、batch-submit、batch-poll，并强调 `--max-seconds` 以避免 openclaw 阻塞
- 大批量支持在 workdir 下按 batch_001/batch_002 分批隔离 inputs/data/state
- 常见问题包含 openclaw `task_id 为 null`、`$RANDOM` 不可用等环境差异
- skill 目录内不包含临时文件（如 `__pycache__`、`.DS_Store`、大体积输出文件）
