---
name: "database-skill-devtest"
description: "开发测试：执行DML/DDL数据变更、表结构变更，涉及工单审批流程。当用户需要修改数据、创建表、修改表结构时调用。"
---

# 开发测试 Skill

此 Skill 用于数据变更（DML）和结构变更（DDL），涉及工单审批流程。

## 依赖文件

- `scripts/dbw_client.py`: HTTP 直连实现，仅依赖 Python 标准库
- `scripts/toolbox.py`: 封装 `create_client` 等函数

## 初始化工具箱

```python
from toolbox import create_client
client = create_client()
```

## 可用方法

### 1. 直接执行 SQL（可能被拦截）
```python
execute_sql(client, sql="UPDATE users SET status=1 WHERE id=100")
```
- **返回**: `{"success": true, "data": {"state": "success", "row_count": N}}`
- **注意**: 如果被安全规则拦截，会返回错误，此时需要创建工单

### 2. 创建 DML 工单（数据变更）
> 📖 **指南**:
> - [MySQL DML 指南](mysql/dml-guide.md)
> - [PostgreSQL DML 指南](postgresql/dml-guide.md)

```python
create_dml_sql_change_ticket(client,
    sql_text="UPDATE users SET status=1 WHERE id=100",
    title="更新用户状态",
    memo="测试数据更新"
)
```
- **返回**: `{"success": true, "data": {"ticket_id": "...", "status": "TicketExamine", "ticket_url": "..."}}`

### 3. 创建 DDL 工单（结构变更）
> 📖 **指南**:
> - [MySQL DDL 指南](mysql/ddl-guide.md)
> - [PostgreSQL DDL 指南](postgresql/ddl-guide.md)

```python
create_ddl_sql_change_ticket(client,
    sql_text="ALTER TABLE users ADD COLUMN email VARCHAR(100)",
    title="添加邮箱字段"
)
```
- **返回**: 同 DML 工单

### 4. 查询工单列表
```python
describe_tickets(client, list_type="CreatedByMe")
```
- **返回**: `{"success": true, "data": {"tickets": [...]}}`

### 5. 查询工单详情
```python
describe_ticket_detail(client, ticket_id="ticket_xxx")
```
- **返回**: `{"success": true, "data": {"status": "...", "result": "..."}}`

### 6. 查询审批流程
```python
describe_workflow(client, ticket_id="ticket_xxx")
```
- **返回**: `{"success": true, "data": {"nodes": [...]}}`

## 工作流

1. **尝试执行**: 先尝试直接执行 `execute_sql`。
2. **创建工单**: 如果被安全规则拦截（或属于高风险操作），则调用 `create_dml_sql_change_ticket` 或 `create_ddl_sql_change_ticket` 创建工单。
3. **等待审批**: 创建工单后，状态通常为 `TicketExamine`（审批中）。
   - **关键步骤**: **必须明确告知用户工单需要审批**。
   - **行动**: 提供审批人信息（从返回结果中获取 `approver`）和工单链接（`ticket_url`），并提示用户："请联系审批人 [姓名] 进行审批，审批链接：[URL]"。
4. **等待执行**: 审批通过后，工单进入 `TicketWaitExecute`（等待执行）状态；工单执行方式固定为 `Manual`（审批后手动执行），**必须由用户在 DBW 控制台手动触发执行**，不会自动跑 SQL。告知用户："审批通过后，请到工单链接中点击「执行」按钮触发变更。"
5. **查询状态**: 使用 `describe_ticket_detail` 查询工单最终执行状态。
