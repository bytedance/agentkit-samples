# Changelog

## 1.0.5

- `VERSION` 与 `SKILL.md` front-matter 版本对齐，修复埋点 `skillVersion` 不一致。
- 自测说明去掉对 Skill 包内不存在目录的硬编码路径，仅保留可执行的 `bytedlive control test` 说明。

## 1.0.4

- `control room list` 的 `--sort-order` 支持 `desc`/`asc` 等小写输入，CLI 自动规范为 OpenAPI 要求的 `Desc`/`Asc`。
- 自测说明与 `bytedlive control test` 对齐。

## 1.0.3

- 启动埋点脚本按 Skill 安装路径自动识别 Agent，避免硬编码 `--agent codex` 导致误报。
- SKILL 启动命令改为 `node tools/report_usage.js`（无需手动传 `--agent`）。

## 1.0.0

- 初始版本，提供控播 onboarding、凭证安全、命令路由、OpenAPI 兜底与错误恢复契约。
