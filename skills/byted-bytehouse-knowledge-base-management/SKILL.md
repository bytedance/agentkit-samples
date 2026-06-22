---
name: byted-bytehouse-knowledge-base-management
description: ByteHouse 知识库的管理能力，包括创建知识库、添加知识库内容、查询知识库
version: 1.0.3
---

# byted-bytehouse-knowledge-base-management

## 描述

ByteHouse Knowledge Base Management，提供 ByteHouse 知识库的管理能力，包括创建知识库、添加知识库内容、查询知识库

## 📁 文件说明

- **SKILL.md** - 本文件，技能主文档
- **create_knowledge_base.py** - 创建知识库脚本
- **recall_knowledge_base.py** - 知识库文件召回脚本
- **upload_file_to_kb.py** - 上传文件到知识库脚本(pdf/md/docx/xlsx)
- **delete_file_from_kb.py** - 删除知识库内容脚本
- **delete_knowledge_base.py** - 删除知识库脚本
- **list_files_in_kb.py** - 查询知识库文件列表脚本
- **list_knowledge_base.py** - 查询知识库列表脚本
- **knowledge_base_chat.py** - 知识库流式问答脚本

## 配置说明
配置保存在 `~/.bytehouse_config.json` ，如果该文件存在且非空，则直接使用文件中的配置。如果不存在，则让用户提供ByteHouse连接信息（ 把这个文档也发给用户，文档里面介绍了如何获取主机地址和密码：https://www.volcengine.com/docs/6517/1121919?lang=zh ）。用户提供信息后，保存到json文件，避免重复向用户请求连接信息。当用户切换ByteHouse集群时，一并修改该文件。
```json
{
   "BYTEHOUSE_HOST": "<ByteHouse-host>",
   "BYTEHOUSE_PASSWORD": "<ByteHouse-password>"
}
```
BYTEHOUSE_HOST（主机地址）和BYTEHOUSE_PASSWORD（密码）**必须由**用户提供

执行 `scripts/export_config.sh` 把配置信息导入环境变量中
```bash
source scripts/export_config.sh
```

## 风险预警
当用户希望删除知识库中的某个文件，或者删除整个知识库时，**必须**提示用户数据不可恢复，向用户再次确认后再执行。

## 前置条件

- Python 3.8+
- uv (已安装在 `/root/.local/bin/uv`)

## 🚀 使用方法

以下是每个脚本的具体使用指令示例。在执行这些脚本前，请确保已经导入了配置：

```bash
# 导入配置
source scripts/export_config.sh
```

### 1. 创建知识库 (`create_knowledge_base.py`)
```bash
python3 scripts/create_knowledge_base.py "我的知识库"
# 可选参数：--description "这是我的知识库描述"
```

### 2. 查询知识库列表 (`list_knowledge_base.py`)
```bash
python3 scripts/list_knowledge_base.py
```

### 3. 上传文件到知识库 (`upload_file_to_kb.py`)
```bash
python3 scripts/upload_file_to_kb.py --kb-id 123 --file ./document.pdf
# 可选参数：--chunk-size 512 --delimiters "#,##" --enable-image-ocr --enable-chunk-auto-merge
```

### 4. 查询知识库文件列表 (`list_files_in_kb.py`)
```bash
python3 scripts/list_files_in_kb.py --kb-id 123
```

### 5. 知识库文件召回 (`recall_knowledge_base.py`)
```bash
python3 scripts/recall_knowledge_base.py --kb-id 123 --query "你的搜索问题"
```

### 6. 知识库流式问答 (`knowledge_base_chat.py`)
```bash
python3 scripts/knowledge_base_chat.py --kb-ids 123 --input "你的提问"
```

### 7. 删除知识库内容 (`delete_file_from_kb.py`)
```bash
python3 scripts/delete_file_from_kb.py --file-id 456
```

### 8. 删除知识库 (`delete_knowledge_base.py`)
```bash
python3 scripts/delete_knowledge_base.py --kb-id 123
```