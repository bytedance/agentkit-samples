# byted-las-video-inpaint 自检清单（Skill Hub）

- SKILL.md 顶部包含 YAML frontmatter（name/description），且无多余分隔符
- 文档不包含任何真实密钥、Token、Cookie（只引用 `LAS_API_KEY` 环境变量名）
- 示例命令均可复制执行，且推荐用 `lasutil <子命令> -h` 核对参数含义
- 批处理示例使用独立 workdir，并支持大批量按 batch_001/batch_002 分批隔离
- 常见问题覆盖 `state.jsonl task_id 为 null`、`$RANDOM` 不可用等环境差异
- skill 目录内不包含临时文件（如 `__pycache__`、`.DS_Store`、大体积输出文件）
