# 【爆款裂变Skill】byted\-kickart\-viral\-replicator 使用手册 

# 如何获取

## ArkClaw 个人版\&企业版

- 请确保您已经完成 ArkClaw 开通和初始化配置

- 安装方式一【自然语言安装】：访问[火山方舟 ArkClaw 控制台](https://console.volcengine.com/arkclaw/chat/)或各类聊天机器人（需已和 ArkClaw 配对），通过询问方式安装

```
帮我安装 byted-kickart-viral-replicator 这个 skill
```



- 安装方式二【使用命令行】:

```
# 示例命令行为火山 Skillhub,可自行替换为 Clawhub 中国站同名 skill
npx skills add https://skills.volces.com/skills/volcengine/kickart -s byted-kickart-viral-replicator --agent openclaw
```

- 安装方式三【压缩包】:访问[火山 Skillhub\-byted\-kickart\-viral\-replicator](https://findskill.com/volcengine/kickart/byted-kickart-viral-replicator) ~~或~~[~~Clawhub 中国站~~](https://cn.clawhub-mirror.com/volcengine-skills/byted-kickart-viral-replicator)获取技能压缩包，下载后通过各类聊天机器人发送，ArkClaw 会自动完成安装

![image\.png](asserts/image%202.png)

## OpenClaw

- 安装方案一【自然语言安装】:请参考[火山 skillhub 指引](https://findskill.com/docs/overview)完成 skillhub 配置；~~或参考~~[~~Clawhub 中国站指引~~](https://cn.clawhub-mirror.com/)~~完成配置~~

```
~~# 示例命令行为火山 Skillhub,可自行替换为 Clawhub 中国站~~
npx skills add vercel/find-skills
```

设置完成后询问 OpenClaw:请帮我安装爆款裂变 skill,根据 ArkClaw 回复和提示，确认安装 byted\-kickart\-viral\-replicator 技能

- 安装方式二【使用命令行】:

```
~~# 示例命令行为火山 Skillhub,可自行替换为 Clawhub 中国站~~
npx skills add https://skills.volces.com/skills/volcengine/kickart -s byted-kickart-viral-replicator --agent openclaw
```

## 其他 AI IDE

- Trae

```
npx skills add https://skills.volces.com/skills/volcengine/kickart -s byted-kickart-viral-replicator --agent trae
```

- Claude Code

```
npx skills add https://skills.volces.com/skills/volcengine/kickart -s byted-kickart-viral-replicator --agent trae
```

# 功能说明

- 支持用户在提及“爆款裂变、爆款克隆、复制视频、克隆视频、同款视频”或表达等价意图时，自动唤醒爆款裂变 Skill，通过对话式交互完成参考视频复刻

- 支持用户提供参考视频（tos 链接或本地上传），并结合目标商品素材（抖店链接、商品图片、商品名称、模特图片），自动完成创意分析与视频成片

- 使用该技能会消耗您的[创作 Agent](https://console.volcengine.com/kickart/welcome) 创点，具体消耗额度和视频时长相关，请遵照技能提示完成默认配置开通（企业版 ArkClaw 支持火山统一鉴权，在企业管理员配置好火山 AK\&SK 后，不需要用户单独配置）

## 触发 Skill

- 当您在对话中提及"爆款复刻、爆款克隆、复制视频、克隆视频、同款视频"等关键词，或表达等价意图时，Skill 将被自动唤醒

- 命中后，Skill 会确认意图、进行前置条件检查，自动校验您 kickart 账号的套餐状态

![image\.png](asserts/image%2010.png)

## 火山鉴权配置

- Skill 启动时会自动校验鉴权

- 若鉴权未配置，Skill 会引导您直接在对话中发送 AK/SK，完成本次会话临时环境变量配置：    

    - 临时配置仅在本次会话生效，不会持久化存储

    - 访问[火山引擎控制台\-密钥管理](https://console.volcengine.com/iam/keymanage)获取 AK/SK

```text
ACCESS_KEY_ID=xxx
SECRET_ACCESS_KEY=xxx
```

## 提供参考视频

- 您可以发送视频 tos 链接，或上传本地视频文件

- 视频规格详见[FAQ](https://bytedance.larkoffice.com/wiki/UeZaw3cj4iMLzqkaQFVcrYAUnoF#share-NvAKdnYJUodRR8x9LWEcyK7pnYf)

![image\.png](asserts/image%204.png)

![image\.png](asserts/image%206.png)

## 提供目标商品素材

- **抖店链接**：支持您输入抖店 Url，Skill 将自动提取目标商品的图片、名称

- **商品图片**：支持手动提供，规格详见[FAQ](https://bytedance.larkoffice.com/wiki/UeZaw3cj4iMLzqkaQFVcrYAUnoF#share-NvAKdnYJUodRR8x9LWEcyK7pnYf)

- **商品名称**：≤30 中文字符

![image\.png](asserts/image%207.png)

## 确认成片信息

- **语种**：默认中文，支持多语种（英文、巴西葡萄牙语）

- **创意分析**：Skill 将展示创意分析（包括卖点、受众、场景等）,您可以使用自然语言进行调整

![image\.png](asserts/image.png)

![image\.png](asserts/image%208.png)

## 数字人模特确认

默认智能匹配数字人用于成片，也支持您上传自定义模特图，规格详见[FAQ](https://bytedance.larkoffice.com/wiki/UeZaw3cj4iMLzqkaQFVcrYAUnoF#share-NvAKdnYJUodRR8x9LWEcyK7pnYf)

- 请上传数字人形象，不要上传明星或公众 IP 形象

![image\.png](asserts/image%201.png)

![image\.png](asserts/image%209.png)

## 费用与合规确认

- **创点消耗**：任务发起后创点消耗不可退还

- **余额校验**：此步会校验您的创点余额

- **合规确认**：发起任务默认已同意 [虚拟人像合规承诺函](https://www.volcengine.com/docs/6664/2369812?lang=zh) 和 [合规承诺函](https://www.volcengine.com/docs/6664/2369383?lang=zh)

![image\.png](asserts/image%203.png)

## 消费成片

- 确认后，Skill 进入成片环节，完成后将返回可下载的 tos 链接

![image\.png](asserts/image%205.png)

# FAQ

Q：企业账号的子账号使用技能时开通报错，如何解决？

A：需要开通对应的产品策略权限，请访问[火山控制台权限策略](https://console.volcengine.com/iam/policymanage)，确保企业账号和子账号均开通授权策略：CreativeAgentOpenapiAccess。若子账号无访问火山控制台权限策略权限，需联系企业账号管理员协助处理。请注意，子账号和火山AK\&SK需要匹配！

---

Q：是否支持使用kickart资产库内的视频来做裂变？

A：不支持

---

Q：成片时长是多少？

A：和输入参考视频的时长相似，最多不超过60s

---

Q：成片步骤时要等待多久？

A：成片涉及到视频生成模型调用，可能长达十几分钟，请耐心等待。

---

Q：每次制作会消耗多少创点？

A：创点消耗与成片时长相关，具体以制作后在创作 Agent 控制台查询为准。

---

Q：创点用完了怎么办？

A:前往 [创点充值页面](https://console.volcengine.com/kickart/fusion/setting/combobuy?tab=additionalCombo) 充值创点或升级套餐。

---

Q：如何获取 Skill 最新版本？

A:可以关注 [Skill 详情页](https://findskill.com/volcengine/kickart/byted-kickart-viral-replicator)或和 ArkClaw 对话检查更新。

---

Q：参考视频和图片有什么格式和尺寸要求？

A：

- 参考视频：MP4 / MOV；单文件 ≤50MB；时长 ≤60s；分辨率 ≥480p；比例 9:16、16:9、3:4、4:3、1:1

- 商品图片：JPEG / PNG;1–10 张；单张 ≤10MB;分辨率 ≥480p；宽×高 9 万 \~ 3600 万像素；宽高比 0\.25–4

- 模特图片：1–3 张，规格同商品图；请上传数字人形象，不要上传明星或公众 IP 形象

---

Q：任务发起后创点可以退还吗？

A：任务发起后创点消耗不可退还，请仔细核对成片信息后再确认发起。

---



> (注：内容由 AI 生成，请谨慎参考）