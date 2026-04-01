---
name: byted-skillhub-upload
description: 上传 Skill（目录或 zip）到 SkillHub 私有或企业专属空间。当需要把本地技能发布到私有或企业专属 SkillHub 时使用。
---

# byted-skillhub-upload

用途
- 将本地 Skill（文件夹或 zip 包）上传到 SkillHub，并创建一个新的 Skill 及版本。
- 上传成功后输出 `Id` 与 `SkillVersionId`。

何时调用
- 当用户需求涉及将本地技能上传/发布到 **企业 SkillHub** 或 **私有技能空间** 时触发。常见语义包括：
  1. 明确要求“上传到 SkillHub / 发布到 SkillHub”。
  2. 提到“企业专属技能空间 / 私有技能空间 / 内部技能”。
  3. 需要将一个本地目录打包后上传为 Skill。

环境说明 (Agent 必读)
- **无需向用户索要环境变量**：当前环境已自动注入以下变量：
  - `ARK_SKILL_API_BASE`: SkillHub API 服务地址
  - `ARK_SKILL_API_KEY`: 企业 SkillHub 访问密钥
  - `SKILLHUB_SKILL_SPACE_ID`: 企业专属技能空间 ID
- **严禁向用户询问参数值**：Agent 在触发此技能时，应直接从环境中读取这些变量并执行脚本，不得中断流程向用户确认这些信息。

上传步骤
1. 确定待上传目标
   - 目标必须是一个目录，或一个以 `.zip` 结尾的文件
   - 若目标是目录，脚本会先将其内容压缩为 zip 包再上传
2. 执行脚本（路径相对于本 SKILL.md 所在目录）
   - 上传目录：`python ./scripts/upload_to_skillhub.py --path "./my-skill" --name "my-skill" --description "demo"`
   - 上传 zip：`python ./scripts/upload_to_skillhub.py --path "./my-skill.zip" --name "my-skill" --description "demo"`
3. 观察输出
   - 成功时会打印两行：
     - `Id: <skill_id>`
     - `SkillVersionId: <skill_version_id>`

示例
- 将 `./skills/my-private-skill/` 上传到 SkillHub：
  - `python ./scripts/upload_to_skillhub.py --path "./skills/my-private-skill" --name "my-private-skill" --description "internal"`

故障排查
- 如提示缺少环境变量，请确认在环境中运行或联系管理员
- 参数错误：确认 `--path` 指向目录或 `.zip` 文件
- 网络或鉴权错误：检查网络连通性与 API Key 是否有效
