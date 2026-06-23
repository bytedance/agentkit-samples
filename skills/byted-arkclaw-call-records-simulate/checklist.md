# byted-arkclaw-call-records-simulate 自检清单（Skill Hub）

- SKILL.md 顶部包含 YAML frontmatter（name / version / description）
- description 用英文关键词覆盖通话记录 / TTS / 合成 / 猎头 / 催收 / 售后 / ASR 测试等场景
- scripts/ 下同时包含 `env_init.sh`、`generate_record.py`、`tts_processor.py`
- `tts_processor.py` 对 JSON 做 schema 校验（`name` / `output_file` / 非空 `conversations`、每轮含 `role/text/voice`）
- 工作流中强制"先生成 JSON → 用户确认 → 再合成音频"两步走
- references/voices.md 说明男女搭配原则，避免同 voice 无法区分说话人
- evals/evals.json 至少覆盖：面试邀约、催收、ASR 测试素材、直接合成已有素材 4 类
- 不在文档或代码中编造真实姓名、真实号码、敏感信息
- skill 目录内不提交 `tts_env/`、`output/*.mp3`、`__pycache__/`、`.DS_Store` 等生成物（通过 .gitignore）
