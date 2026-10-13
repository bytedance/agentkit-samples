# byted-arkclaw-local-batch-asr 自检清单（Skill Hub）

- `SKILL.md` 顶部包含 YAML frontmatter（`name` / `version` / `description`）
- `description` 明确说明是本地批量 ASR，并指出适用场景与触发时机
- `scripts/` 下至少包含 `env_init.sh`、`check_format.sh`、`transcribe_batch.py`、`generate_result.md.sh`
- 所有执行相关代码均集中在 `scripts/` 下，避免在 skill 根目录放独立运行时代码目录
- `SKILL.md` 中明确体现 skill 的目录约定：`SKILL.md` 为入口，`scripts/` 放代码，`references/` 放资料
- 文档中明确说明与 `byted-las-asr-pro` 的替换关系与能力差异
- 支持单文件、目录、manifest 三种输入方式
- 支持生成 `summary.json` 和 `summary.csv` 两种汇总结果
- skill 目录内不提交 `.venv/`、`output/`、`__pycache__/`、`.DS_Store` 等生成物
