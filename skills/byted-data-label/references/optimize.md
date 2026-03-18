# SKILL: seederive-optimize

> Seederive 提示词优化 SKILL —— 教会 Agent 通过错题管理和提示词优化来提升任务效果

## 触发条件

当用户提到以下意图时触发：
- 任务效果不好，需要优化（如"这个任务效果不好，帮我优化"）
- 上传错题/标注错误案例（如"这些结果不对，帮我上传错题"）
- 优化提示词（如"帮我优化一下提示词"）
- 查看优化报告（如"优化结果怎么样"）
- 切换模型（如"换个模型试试"）
- 生成提示词（如"帮我写一个提示词"）

## 前置条件

- 确保已完成 `SKILL.md` 中的前置步骤（设置 `VOLCENGINE_ACCESS_KEY` 和 `VOLCENGINE_SECRET_KEY`）
- 已创建任务（需要 taskId 和 nodeId），详见 `${SKILL_DIR}/references/task.md`

## 脚本命令速查

### 错题管理

| 操作 | 命令 |
|------|------|
| 上传错题（文本） | `python ${SKILL_DIR}/scripts/seederive.py error-case create-text --task-id 123 --node-id emotion_1 --items-file items.json` |
| 上传错题（文件） | `python ${SKILL_DIR}/scripts/seederive.py error-case create-file --task-id 123 --file errors.csv` |
| 查询错题列表 | `python ${SKILL_DIR}/scripts/seederive.py error-case list --task-id 123` |
| 删除错题 | `python ${SKILL_DIR}/scripts/seederive.py error-case delete --ids 1,2,3` |
| 下载错题模板 | `python ${SKILL_DIR}/scripts/seederive.py error-case template --format csv` |

### 提示词管理

| 操作 | 命令 |
|------|------|
| 查询提示词详情 | `python ${SKILL_DIR}/scripts/seederive.py prompt detail --task-id 123 --node-id emotion_1` |
| 生成提示词 | `python ${SKILL_DIR}/scripts/seederive.py prompt generate --description "分析商品评论的情感"` |
| 触发优化 | `python ${SKILL_DIR}/scripts/seederive.py prompt optimize --task-id 123` |
| 查询优化报告 | `python ${SKILL_DIR}/scripts/seederive.py prompt report --task-id 123 --node-id emotion_1` |

### 模型管理

| 操作 | 命令 |
|------|------|
| 查询可用模型 | `python ${SKILL_DIR}/scripts/seederive.py model list` |
| 修改节点模型 | `python ${SKILL_DIR}/scripts/seederive.py model set-node --task-id 123 --node-id emotion_1 --model-id 2 --temperature 0.3` |

## 优化流程

完整的优化闭环分为四步：**上传错题 → 触发优化 → 查看报告 → 应用优化**

```
1. 查看当前提示词      →  python ${SKILL_DIR}/scripts/seederive.py prompt detail ...
2. 上传错题           →  python ${SKILL_DIR}/scripts/seederive.py error-case create-text/create-file ...
3. 触发优化           →  python ${SKILL_DIR}/scripts/seederive.py prompt optimize ...
4. 查看优化报告        →  python ${SKILL_DIR}/scripts/seederive.py prompt report ...
5.（可选）切换模型     →  python ${SKILL_DIR}/scripts/seederive.py model list → model set-node ...
6. 回到 seederive-task 重新执行任务验证效果
```

## 执行步骤

### 场景一：发现效果不好，上传错题并优化

用户说："这个任务效果不好，帮我优化"

**步骤一**：执行脚本，查看当前提示词状态

```bash
python ${SKILL_DIR}/scripts/seederive.py prompt detail --task-id 123 --node-id emotion_1
```

**步骤二**（Agent 模型能力）：分析任务结果，识别哪些结果不准确，整理为错题格式

**步骤三**（Agent 模型能力）：构造错题 JSON 文件 `items.json`

错题项格式：
```json
[
  {
    "input": "userTemplate=这个产品真的太烂了，永远不会再买",
    "actualOutput": "中性",
    "expectedOutput": "负面"
  },
  {
    "input": "userTemplate=还行吧，一般般",
    "actualOutput": "正面",
    "expectedOutput": "中性"
  }
]
```

> **注意**：`input` 字段的格式为 `占位符名=值`。占位符名需要与提示词中的占位符一致，大部分情况下为 `userTemplate`。

**步骤四**：执行脚本，上传错题

```bash
python ${SKILL_DIR}/scripts/seederive.py error-case create-text --task-id 123 --node-id emotion_1 --items-file items.json
```

**步骤五**：执行脚本，触发提示词优化

```bash
python ${SKILL_DIR}/scripts/seederive.py prompt optimize --task-id 123
```

**步骤六**：执行脚本，查询优化报告（优化是异步的，需要等待完成）

```bash
python ${SKILL_DIR}/scripts/seederive.py prompt report --task-id 123 --node-id emotion_1
```

**步骤七**（Agent 模型能力）：分析优化报告中的 score 和 analysis，判断是否达标。如果达标，建议用户回到 `seederive-task` 重新执行任务。

### 场景二：通过文件上传错题

用户说："我有一个 CSV 文件，里面是标注好的错题"

**步骤一**：执行脚本，下载错题模板（可选，帮助用户了解格式）

```bash
python ${SKILL_DIR}/scripts/seederive.py error-case template --format csv
```

模板包含列：`task_id`, `field`, `input`, `actual_output`, `expected_output`

**步骤二**：执行脚本，上传错题文件

```bash
python ${SKILL_DIR}/scripts/seederive.py error-case create-file --task-id 123 --file /path/to/errors.csv
```

**步骤三**：继续触发优化（同场景一的步骤五）

### 场景三：查看并管理错题

**查询错题列表**：

```bash
python ${SKILL_DIR}/scripts/seederive.py error-case list --task-id 123 --page 1 --page-size 20
```

返回中 `promptOptStatus` 状态码含义：

| 状态码 | 含义 |
|-------|------|
| 0 | 等待优化 |
| 1 | 提交中 |
| 2 | 优化中 |
| 3 | 优化成功 |
| 4 | 优化失败 |

**删除错题**（只有在优化状态为"成功"或"失败"时才允许删除）：

```bash
python ${SKILL_DIR}/scripts/seederive.py error-case delete --ids 1,2,3
```

### 场景四：切换模型

用户说："换个模型试试"

**步骤一**：执行脚本，查看可用模型

```bash
python ${SKILL_DIR}/scripts/seederive.py model list
```

**步骤二**（Agent 模型能力）：根据任务需求推荐合适的模型

**步骤三**：执行脚本，修改节点的模型配置

```bash
python ${SKILL_DIR}/scripts/seederive.py model set-node --task-id 123 --node-id emotion_1 --model-id 2 --temperature 0.3 --max-token 4096
```

### 场景五：生成提示词

用户说："帮我写一个分析商品评论的提示词"

```bash
python ${SKILL_DIR}/scripts/seederive.py prompt generate --description "分析电商商品评论，提取用户对产品质量、价格、物流的评价"
```

## 错误处理

| 错误关键词 | 含义 | 处理建议 |
|-----------|------|---------|
| "当前任务正在优化中" | 优化进行中 | 等待完成后再操作 |
| "错题未发生新增或删除" | 无新错题 | 需要先上传新错题才能触发优化 |
| "当前提示词优化未完成" | 优化中 | 等待优化完成后再删除错题 |

## 与其他 SKILL 的关系

- 本 SKILL 依赖已创建的任务（需要 taskId 和 nodeId），详见 `${SKILL_DIR}/references/task.md`
- 优化完成后，建议用 quick-preview 验证效果，或读取 `${SKILL_DIR}/references/task.md` 重新执行任务
