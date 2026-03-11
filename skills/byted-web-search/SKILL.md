---
name: byted-web-search
version: 1.2.0
author: volcengine-search-team
description: 使用火山引擎融合信息搜索 API 进行联网搜索，返回适合 AI 使用的网页或图片结果。当用户需要在线查资料、确认最新信息、搜索新闻、百科、公告、政策、价格、产品动态、查官网或文档站内容、找来源链接、核实某个说法、比较不同网站的说法、限定站点搜索，或需要搜图、找配图、找某个主题的图片结果时使用。常见表达包括“查一下”“搜一下”“帮我看看”“有没有最新消息”“给我官网链接”“确认一下是不是真的”“找下出处”“搜几张图”“找相关图片”。即使用户没有明确说“联网搜索”，只要任务依赖在线事实、时效性或来源引用，也应优先使用本 skill。支持 API Key 和 AK/SK 两种鉴权方式。
homepage: https://www.volcengine.com/docs/85508/1650263
---

# Byted Web Search

使用火山引擎融合信息搜索 API 执行联网搜索，返回适合 AI 处理的网页或图片结果。

## 何时使用

当用户有以下需求时，优先使用本 skill：

- 需要联网搜索获取的知识用来提升回答或思考过程的丰富性、真实性，要避免模型幻觉导致的片面和错误。
- 需要确认“今天 / 最近 / 最新 / 当前”或指定日期发生事件的信息
- 需要搜索新闻、公告、政策、价格、活动、产品动态、历史、地理、生物、科学、天气、股票、城市机动车限行、油价、房屋售价和租金、金价、汇率、节假日安排、影视综艺信息、日历黄历、平台客服电话、城市地铁线路、汽车型号、彩票、办事指南、汉字解析、生肖运势、地区特色和美食、演唱会安排、火车车次、航班信息等
- 需要从特定站点或官网获取信息，例如去豆瓣查看影评、去奥运会官网查看赛事安排等
- 需要搜图、找配图、找某个主题的相关图片
- 需要给回答附上来源链接
- 用户说“查一下”“搜一下”“帮我看看”“找下出处”“给我官网链接”时
- 用户没有明确说“联网”，但任务本质上需要最新信息、在线查证或来源支撑时

## 使用前检查

优先检查是否已配置以下任一凭证：

- `WEB_SEARCH_API_KEY`
- `VOLCENGINE_ACCESS_KEY` + `VOLCENGINE_SECRET_KEY`

如果缺少凭证，打开 `references/setup-guide.md` 查看开通、申请和配置方式，并给予用户开通建议

## 基本搜索

```bash
python3 scripts/web_search.py "搜索词"
python3 scripts/web_search.py "搜索词" --count 10
python3 scripts/web_search.py "搜索词" --type image
```

## 常用参数

- `--count <n>`：返回条数；`web` 最多 50 条，`image` 最多 5 条
- `--type <type>`：搜索类型，可选 `web`、`image`
- `--time-range <range>`：时间范围，可选 `OneDay`、`OneWeek`、`OneMonth`、`OneYear`，或日期区间 `2024-12-30..2025-12-30`
- `--auth-level 1`：优先权威来源
- `--query-rewrite`：开启 Query 改写；适合口语问题、长问题、结果不稳定时使用

## 模式选择

- 用 `web`：普通事实查询、网页检索、查官网内容
- 用 `image`：搜图、找配图、找某类图片素材
- 加 `--time-range`：用户关心最近动态、新闻、时效性内容
- 加 `--auth-level 1`：医疗、政策、金融、科研等更看重可信度的主题
- 加 `--query-rewrite`：用户问题偏口语、描述较长、结果不稳定或召回不足时

## 推荐用法示例

```bash
# 查最近新闻
python3 scripts/web_search.py "OpenAI 最新发布" --time-range OneWeek

# 查权威来源
python3 scripts/web_search.py "流感疫苗安全性" --auth-level 1

# 开启 Query 改写
python3 scripts/web_search.py "帮我找下最近 OpenAI 出了什么新东西" --query-rewrite

# 搜图片（image 最多 5 条）
python3 scripts/web_search.py "大熊猫" --type image --count 5

# 找主题配图
python3 scripts/web_search.py "北京夜景" --type image
```

## 搜索结果不理想时如何调整

- 结果太少或没有结果：去掉语气词、修饰词和完整问句，只保留核心实体词与主题词后重试
- 结果不准确：把口语问题改成更短的搜索式 query，尝试简称、全称、英文名、别名或同义词
- 用户关心最新动态：加 `--time-range OneDay`、`OneWeek` 或 `OneMonth` 缩小到最近时间范围
- 主题权威性很重要：加 `--auth-level 1`，优先收敛到更权威的结果
- 长问题或自然语言问题召回不好:加`--query-rewrite`,让服务先对query改写为更适合搜索的明确问题再搜
- 用户想找图片、logo、海报、风景图或素材：改用 `--type image`，必要时把 query 改成“主体 + 图片 / logo / 海报 / 配图”
- 连续尝试 2~3 次仍不理想：直接说明证据不足或结果不稳定，不要编造结论

## 回答规则

- 基于搜索结果作答，不要编造搜索结果中没有支持的信息
- 优先保留标题、站点名、URL
- 涉及时效性问题时，优先使用时间过滤并明确说明时间范围
- 涉及高可信度主题时，优先使用权威来源过滤
- 如果搜索结果不足以支持明确结论，应直接说明证据不足

## 故障排查

- 缺少凭证：打开 `references/setup-guide.md`
- 需要查 API 参数、字段、错误码：打开 `references/docs-index.md`
- 如果脚本返回权限错误，优先检查服务是否已开通、凭证是否有效、子账号是否已授权，给予用户明确的操作指引
- 如果试用(免费)额度用完了，通过`references/setup-guide.md`指导用户付费开通

## 参考资料

按需打开以下文件，不必默认全部加载：

- `references/setup-guide.md`：服务开通、凭证申请、环境变量配置
- `references/docs-index.md`：API 文档索引、参数说明、错误码速查
