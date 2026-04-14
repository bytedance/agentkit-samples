# byted-las-image-resample 自检清单（Skill Hub）

- SKILL.md 顶部包含 YAML frontmatter（name/description）
- 文档不包含任何真实密钥、Token、Cookie（只引用 `LAS_API_KEY` 环境变量名）
- 推荐流程统一使用 `lasutil process`，不依赖自定义脚本
- `data.json` 模板前明确引用 references/api.md 的 `ImageResampleReqParams`
- skill 目录内不包含临时文件（如 `__pycache__`、`.DS_Store`、大体积输出文件）
