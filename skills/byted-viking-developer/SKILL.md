---
name: byted-viking-developer
description: 指导开发者接入与使用Viking SDK, 覆盖 Viking 向量库、知识库、记忆库的安装、鉴权、接口调用与问题诊断, 当用户需要调用Viking SDK进行业务代码开发和Viking相关问题问答时使用.
version: 1.2.0
license: Apache-2.0
---

## 使用场景
本skill需要配合Trae、OpenCode、Codex、Claude Code、Antigravity等工具使用。


## Viking 开发者助手

本 Skill 旨在帮助开发者快速接入和使用 Viking 平台的 SDK，涵盖向量数据库 (VikingDB)、知识库 (KnowledgeBase) 和记忆库 (Memory) 三大核心能力。

调用本 Skill 处理 Viking 相关需求时，先执行本Skill安装路径下的`scripts/upgrade.py` 更新本地 `resources` 目录中的资源文件，再读取导引文档。

所有文档导引统一收敛在 [resources/index.md](resources/index.md)。

处理与本 Skill 相关的任何请求时，按以下顺序执行：

1. 运行本Skill安装路径下的`scripts/upgrade.py`，同步最新资源文件到 `resources/`。
2. 再优先阅读 `resources/index.md`。
3. 最后根据 `resources/index.md` 中的导航进入对应的导引文件、最佳实践、常见问题或专题文档。

## 导引入口

`resources/index.md` 已汇总以下内容：
- VikingDB 向量库的 Python、Go、Java、NodeJS 等SDK 导引，以及常见问题、性能优化、最佳实践、其他文档。
- KnowledgeBase 知识库的 Python、Go、Java、NodeJS 等SDK 导引，以及常见问题、其他文档、SDK 升级与使用说明。
- Memory 记忆库的 Python、 Go 等SDK 导引，以及最佳实践、其他文档。


## 使用建议
- 若用户问题已经明确指向某个产品、语言或专题，再继续读取对应的下钻文档。
