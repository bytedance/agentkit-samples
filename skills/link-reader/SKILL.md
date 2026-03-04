---
name: link-reader
description: 使用内置 link_reader 函数读取网页、PDF或抖音视频内容。准备 URL 列表。运行脚本 `python scripts/link_reader.py "url1" "url2" ...`。
license: Complete terms in LICENSE.txt
---

# Link Reader

## 适用场景

当需要获取网页、PDF 或抖音视频的标题和正文内容时，使用该技能调用 `link_reader` 函数。

## 认证与凭据来源

- 用户首次使用本技能时，先检查是否配置了`ARK_API_KEY`和`MODEL_AGENT_API_KEY`环境变量，如未配置，提示用户需要提供`ARK_API_KEY`，并把它写入到workspace下的环境变量文件中，如果文件已存在则追加到末尾，确保环境变量格式正确，使这个环境变量生效
- 该技能默认使用 `ARK_API_KEY` 环境变量
- 若未配置，将尝试使用 `MODEL_AGENT_API_KEY` 环境变量。

## 使用步骤

1. 准备 URL 列表。
2. 运行脚本 `python scripts/link_reader.py "url1" "url2" ...`。运行之前cd到对应的目录。
3. 返回结果包含每个 URL 的标题和内容。

## 输出格式

- JSON 格式的列表，每个元素包含 URL 对应的标题和内容。

## 错误处理

- 如果出现'PermissionError: ARK_API_KEY or MODEL_AGENT_API_KEY is not set in environment variables.'错误，则提示用户需要提供`ARK_API_KEY`或`MODEL_AGENT_API_KEY`，并把它们写入到workspace下的环境变量文件中，如果文件已存在则追加到末尾，确保环境变量格式正确，使这个环境变量生效，并重试刚才失败的读取。
- 再次使用本技能时，优先从环境变量中读取`ARK_API_KEY`或`MODEL_AGENT_API_KEY`

## 示例

```bash
python scripts/link_reader.py "https://example.com"
```
