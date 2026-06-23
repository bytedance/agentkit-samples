---
name: dice-roller
description: 一个简单的掷骰子工具。用于生成随机数，或在用户纠结时做“玄学推荐”。
version: 1.0.0
entrypoint: python roll.py
args:
    sides:
        type: int
        description: 骰子的面数（默认为 6）。
        required: false
    count:
        type: int
        description: 掷骰子的数量（默认为 1）。
        required: false
output:
    type: json
    description: 返回掷骰子的结果，包括每次投掷的点数和总和。
---

# 掷骰子工具 (Dice Roller)

这是一个简单的掷骰子工具。

## 功能
- 支持自定义骰子面数（默认为 6 面）。
- 支持自定义掷骰子数量（默认为 1 个）。
- 返回每次投掷的结果和总和。

## 参数说明
- `sides`: 骰子面数 (Integer)
- `count`: 骰子数量 (Integer)

## 返回示例
```json
{
    "status": "success",
    "results": [3, 5],
    "total": 8,
    "details": "Rolled 2d6"
}
```
