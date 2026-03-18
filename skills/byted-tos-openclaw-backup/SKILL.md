---
name: byted-tos-openclaw-backup
description: 自动备份OpenClaw核心配置、技能文件和记忆数据到挂载的TOS网盘，按日期分类存储，自动跳过依赖目录和可执行文件。当你需要创建或恢复OpenClaw环境备份时使用此技能。
metadata:
  openclaw:
    emoji: "💾"
    requires: { "bins": ["df", "grep", "find", "du", "awk", "sed", "bc"] }
---

# OpenClaw 自动备份技能

此技能帮助你自动备份OpenClaw的核心配置、技能源码和记忆数据到挂载的TOS网盘，按日期创建备份目录，自动跳过依赖目录和大体积可执行文件。

## 何时使用

当用户要求执行以下操作时使用此技能：
- "备份OpenClaw配置"
- "备份技能文件"
- "备份到网盘"
- "创建系统备份"
- "定期备份"

## 备份策略

### 备份内容
1. **核心配置文件**：工作区根目录下所有MD文档（AGENTS.md, SOUL.md, USER.md等）
2. **系统配置**：`/root/.openclaw/config/`目录下的JSON/YAML/ENV/conf等配置文件，跳过二进制文件
3. **技能文件**：扩展技能和工作区技能的源码文件（JS/TS/PY/MD/JSON/YAML/SH），自动跳过以下目录：
   - `node_modules/`
   - `venv/`
   - `__pycache__/`
   - `dist/`
   - `build/`
4. **记忆数据**：`/root/.openclaw/workspace/memory/`目录下的所有记忆文件

### 存储结构
```
my-bucket/
└── openclaw_backup/
    ├── 2026-03-11/
    │   ├── *.md                    # 核心配置文件
    │   ├── config/                 # 系统配置
    │   ├── skills/
    │   │   ├── extensions/         # 扩展技能源码
    │   │   └── workspace/          # 工作区技能源码
    │   ├── memory/                 # 记忆数据
    │   ├── backup_summary.txt      # 备份统计信息
    │   └── backup_manifest.txt     # 完整文件清单
    └── 2026-03-12/
        └── ...
```

## 指令

### 1. 执行完整备份

运行备份脚本自动完成所有备份操作：

```bash
scripts/backup.sh
```

**输出示例：**
```text
🔍 检测可用网盘...
✅ 自动选择存储桶: my-bucket (/root/.openclaw/workspace/my-bucket)
ℹ️  所有可用存储桶:
  - my-bucket: /root/.openclaw/workspace/my-bucket
💡 如需固定使用某个存储桶，请运行: bash scripts/config.sh <存储桶名称>

📂 创建备份目录: /root/.openclaw/workspace/my-bucket/openclaw_backup/2026-03-11

📝 备份核心配置文件 (MD文档)...
✅ 核心配置文件备份完成 (7 个文件)

⚙️  备份系统配置 (仅配置文件，跳过二进制)...
🔍 扫描系统配置子目录...
✅ 备份目录: agents (大小: 228K, 文件数: 5)
✅ 备份目录: canvas (大小: 8.0K, 文件数: 1)
✅ 备份目录: completions (大小: 460K, 文件数: 4)
✅ 备份目录: cron (大小: 12K, 文件数: 2)
⚠️  跳过目录: extensions (大小: 2.4G, 文件数: 67554 - 超过阈值)
✅ 备份目录: identity (大小: 8.0K, 文件数: 1)
⚠️  跳过目录: logs (排除列表)
✅ 备份目录: memory (大小: 44K, 文件数: 5)
⚠️  跳过目录: workspace (排除列表)
✅ 系统配置备份完成 (21 个文件)

🔧 备份技能文件 (仅源码文件，跳过node_modules等依赖目录)...
✅ 技能文件备份完成

🧠 备份记忆数据...
ℹ️  记忆目录不存在，跳过记忆数据备份
✅ 记忆数据备份完成

📊 生成备份统计...

✅ 备份完成！
📦 备份桶: my-bucket
📂 备份路径: openclaw_backup/2026-03-11
📄 备份文件数: 463
💾 总大小: 3.6M

📋 备份摘要已保存到: backup_summary.txt
📑 完整文件清单已保存到: backup_manifest.txt
```

### 2. 配置默认存储桶

固定使用某个存储桶进行备份：

```bash
scripts/config.sh <存储桶名称>
```

**示例：**
```bash
scripts/config.sh my-bucket
```

### 3. 检查备份历史

列出所有已创建的备份：

```bash
scripts/list_backups.sh
```

**输出示例：**
```text
📋 现有备份列表 (存储桶: my-bucket):
=====================================
📅 2026-03-11 (463 files, 3.6M)
📅 2026-03-10 (452 files, 3.4M)
📅 2026-03-09 (441 files, 3.2M)
```

### 4. 恢复备份

从指定日期的备份恢复系统：

```bash
scripts/restore.sh <备份日期>
```

**预览恢复（不实际修改文件）：**
```bash
scripts/restore.sh 2026-03-11 --dry-run
```

**输出示例：**
```text
✅ 自动选择存储桶: my-bucket (/root/.openclaw/workspace/my-bucket)
📂 准备恢复备份: 2026-03-11
📦 存储桶: my-bucket
📂 备份路径: /root/.openclaw/workspace/my-bucket/openclaw_backup/2026-03-11

⚠️  恢复操作会覆盖现有文件，确定要继续吗? (y/N) y

🔄 开始恢复...
📝 恢复核心配置文件...
⚙️  恢复系统配置...
✅ 系统配置恢复完成
🔧 恢复技能文件...
✅ 技能文件恢复完成
🧠 恢复记忆数据...
✅ 记忆数据恢复完成

✅ 恢复完成！
📅 恢复的备份日期: 2026-03-11
⚠️  建议重启OpenClaw服务以应用所有配置
```

### 3. 反馈格式

向用户反馈备份结果时使用以下格式：
> "✅ 备份已成功完成！
> 
> ### 📦 备份详情
> - **存储桶**: my-bucket
> - **备份路径**: `openclaw_backup/2026-03-11/`
> - **备份文件数**: 15,076 个
> - **总大小**: 922 MB
> 
> ### 📋 备份内容包含：
> 1. 核心配置文件（工作区所有MD文档）
> 2. 系统配置（JSON/YAML/ENV等配置文件，跳过二进制文件）
> 3. 技能源码（JS/TS/PY/MD等源码文件，自动跳过依赖目录）
> 4. 记忆数据"

## 注意事项

1. 自动检测挂载的网盘，默认使用第一个检测到的存储桶
2. 如果未检测到网盘，提示用户在arkClaw界面配置TOS存储桶
3. 自动跳过可执行文件、依赖目录和大体积二进制文件
4. 每次备份自动创建新的日期目录，不会覆盖历史备份
