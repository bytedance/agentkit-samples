# Workflows

## 1. 初次巡检

1. 先运行 `list-workspaces`
2. 再用 `describe-workspace` 查看目标状态
3. 需要连接信息时，用 `get-workspace-url` 和 `get-keys`

## 2. 安全变更流程

1. 先 `list-branches` 确认现状
2. 用 `create-branch` 创建隔离分支
3. 在分支上执行 SQL / migration / function 部署
4. 用查询动作确认结果
5. 如有问题，再 `reset-branch` 或删除分支

## 3. 数据库排障

1. `list-tables` 确认 schema / table
2. `list-extensions` 确认扩展
3. 用 `execute-sql` 做临时查询
4. 可复用 schema 变更使用 `apply-migration`

## 4. Edge Function 发布

1. `list-edge-functions`
2. `get-edge-function`
3. `deploy-edge-function`
4. 再次查询确认发布结果

## 5. Storage 管理

1. `list-storage-buckets`
2. `get-storage-config`
3. `create-storage-bucket`
4. 删除前确认数据影响
