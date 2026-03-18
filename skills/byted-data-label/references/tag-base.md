# SKILL: seederive-tag-base

> Seederive 标签库管理 SKILL —— 教会 Agent 创建和管理标签体系，为标签识别和主体识别提供分类依据

## 触发条件

当用户提到以下意图时触发：
- 创建标签体系/标签库（如"帮我建一个商品分类的标签体系"）
- 管理已有标签库（如"看看我的标签库"）
- 上传标签文件（如"我有一个标签分类 CSV，帮我上传"）
- 测试标签召回效果（如"测一下这个标签库能不能准确分类"）

## 前置条件

确保已完成 `SKILL.md` 中的前置步骤（设置 `VOLCENGINE_ACCESS_KEY` 和 `VOLCENGINE_SECRET_KEY`）。

## 脚本命令速查

| 操作 | 命令 |
|------|------|
| 上传标签文件 | `python ${SKILL_DIR}/scripts/seederive.py tag-base upload --file tags.csv` |
| 创建标签库 | `python ${SKILL_DIR}/scripts/seederive.py tag-base create --name "名称" --type tag --doc-info '[...]'` |
| 编辑标签库 | `python ${SKILL_DIR}/scripts/seederive.py tag-base update --id 42 --name "新名称"` |
| 标签库详情 | `python ${SKILL_DIR}/scripts/seederive.py tag-base get --id 42` |
| 标签库列表 | `python ${SKILL_DIR}/scripts/seederive.py tag-base list` |
| 召回测试 | `python ${SKILL_DIR}/scripts/seederive.py tag-base retrieval-test --id 42 --question "测试文本"` |
| 删除标签库 | `python ${SKILL_DIR}/scripts/seederive.py tag-base delete --id 42` |

## 核心概念

### 标签库类型

| 类型 | 值 | 用途 | 配合节点 |
|------|---|------|---------|
| 标签分类 | `tag` | 按标签体系对文本进行分类 | TAG_DETECTION |
| 主体识别 | `subject` | 识别文本中提及的实体/品牌 | SUBJECT_DETECTION |

### 标签库文件格式

**标签分类（tag）模板**：

| 一级标签 | 一级标签说明 | 二级标签 | 二级标签说明 | 三级标签 | 三级标签说明 | 四级标签 | 四级标签说明 |
|---------|------------|---------|------------|---------|------------|---------|------------|
| 服务 | 对XX产品售前售中售后的服务评价 | 售后服务 | 对XX产品售后服务的评价 | 维修服务 | 对XX产品售后服务中维修服务的评价 | 维修专业度 | 对XX产品维修服务是否专业的评价 |

- 一级标签为必填，二级三级四级标签选填
- 标签最多支持四级层级

**主体识别（subject）模板**：

| 一级主体 | 一级主体说明 | 二级主体 | 二级主体说明 | 三级主体 | 三级主体说明 |
|---------|------------|---------|------------|---------|------------|
| 集团名 | XX集团也可能被称为XXX | 公司名 | XX公司也可能被称为XXX | 产品名 | XX公司也可能被称为XXX |

- 一级主体为必填，二级三级主体选填
- 主体最多支持三级层级

### 创建标签库的完整流程

```
1. 上传标签文件         →  python ${SKILL_DIR}/scripts/seederive.py tag-base upload --file tags.csv
2. 创建标签库           →  python ${SKILL_DIR}/scripts/seederive.py tag-base create --name "..." --type tag --doc-info '[...]'
3. 召回测试            →  python ${SKILL_DIR}/scripts/seederive.py tag-base retrieval-test --id 42 --question "..."
4. 在任务中使用         →  seederive-task 中的 TAG_DETECTION/SUBJECT_DETECTION 节点引用 tagBaseId
```

## 执行步骤

### 场景一：创建标签分类库

用户说："帮我建一个商品评论的标签体系"

**步骤一**（Agent 模型能力）：根据用户描述，判断标签库类型（tag 或 subject）和标签体系结构

**步骤二**：执行脚本，上传标签文件

如果用户提供了文件：

```bash
python ${SKILL_DIR}/scripts/seederive.py tag-base upload --file /path/to/商品标签.csv
```

返回示例（JSON 输出）：
```json
{
  "code": 0,
  "data": {
    "fileId": "file_abc123",
    "fileName": "商品标签.csv"
  }
}
```

> 记录返回的 `fileId`，下一步创建标签库时需要用到。

**步骤三**：执行脚本，创建标签库

```bash
python ${SKILL_DIR}/scripts/seederive.py tag-base create \
  --name "商品评论标签体系" \
  --type tag \
  --description "用于对商品评论进行多维度标签分类" \
  --doc-info '[{"fileId":"file_abc123","fileName":"商品标签.csv"}]'
```

返回示例：
```json
{
  "code": 0,
  "data": {
    "id": 42,
    "name": "商品评论标签体系",
    "type": "tag",
    "kbId": "kb_xyz789",
    "docInfo": [{ "fileId": "file_abc123", "docId": "doc_456", "fileName": "商品标签.csv" }]
  }
}
```

> 记录返回的 `id`（即 tagBaseId），后续在 seederive-task 的 TAG_DETECTION 节点中使用。

**步骤四**：执行脚本，测试标签召回效果

```bash
python ${SKILL_DIR}/scripts/seederive.py tag-base retrieval-test --id 42 --question "这个手机壳质量很差，用了两天就裂了"
```

**步骤五**（Agent 模型能力）：分析召回结果中的 chunks 和 score，判断标签匹配是否准确。如果准确，告知用户标签库已就绪，可以在创建任务时使用 `tagBaseId: 42`。

### 场景二：创建主体识别库

用户说："帮我建一个汽车品牌的主体库"

**步骤一**：执行脚本，上传主体文件

```bash
python ${SKILL_DIR}/scripts/seederive.py tag-base upload --file /path/to/汽车品牌.csv
```

**步骤二**：执行脚本，创建主体库

```bash
python ${SKILL_DIR}/scripts/seederive.py tag-base create \
  --name "汽车品牌主体库" \
  --type subject \
  --description "识别评论中提及的汽车品牌和车型" \
  --doc-info '[{"fileId":"file_def456","fileName":"汽车品牌.csv"}]'
```

**步骤三**：执行脚本，召回测试

```bash
python ${SKILL_DIR}/scripts/seederive.py tag-base retrieval-test --id 43 --question "刚提了小鹏G6顶配版，续航真的扎实"
```

### 场景三：查看和管理标签库

**查看标签库列表**：

```bash
python ${SKILL_DIR}/scripts/seederive.py tag-base list
```

按类型过滤：

```bash
python ${SKILL_DIR}/scripts/seederive.py tag-base list --type tag --page-num 1 --page-size 10
```

**查看标签库详情**：

```bash
python ${SKILL_DIR}/scripts/seederive.py tag-base get --id 42
```

**编辑标签库**：

```bash
python ${SKILL_DIR}/scripts/seederive.py tag-base update --id 42 --name "商品评论标签体系（v2）" --description "更新后的标签体系"
```

**删除标签库**：

```bash
python ${SKILL_DIR}/scripts/seederive.py tag-base delete --id 42
```

### 场景四：更新标签库文件

用户说："标签体系有更新，帮我换个新文件"

**步骤一**：执行脚本，上传新文件

```bash
python ${SKILL_DIR}/scripts/seederive.py tag-base upload --file /path/to/商品标签_v2.csv
```

**步骤二**：执行脚本，更新标签库（替换文件）

```bash
python ${SKILL_DIR}/scripts/seederive.py tag-base update --id 42 --doc-info '[{"fileId":"file_new789","fileName":"商品标签_v2.csv"}]'
```

> 注意：`doc-info` 中只包含新文件时，旧文件会被自动删除。如果要保留旧文件，需要同时包含旧文件和新文件的信息。

**步骤三**：执行脚本，重新测试召回效果

```bash
python ${SKILL_DIR}/scripts/seederive.py tag-base retrieval-test --id 42 --question "测试文本"
```

## 错误处理

| 错误关键词 | 含义 | 处理建议 |
|-----------|------|---------|
| "标签库名称已存在" | 名称重复 | 换一个名称 |
| "标签库不存在" | ID 错误 | 确认标签库 ID |
| "file 不能为空" | 文件为空 | 检查文件路径 |

## 与其他 SKILL 的关系

- 标签库创建后获得的 `tagBaseId` 用于任务中的 `TAG_DETECTION` 和 `SUBJECT_DETECTION` 节点
- 标签库创建不是必须前置：只有任务需要标签分类或主体识别功能时才需要创建标签库
- 典型流程：先创建标签库 → 读取 `${SKILL_DIR}/references/task.md` 创建任务 → 效果不佳时读取 `${SKILL_DIR}/references/optimize.md` 优化
