# BytePlus AgentKit 示例 / BytePlus AgentKit Examples

本目录包含一组专门面向 **BytePlus** 客户、并在 BytePlus 平台上实际测试过的 AgentKit 示例。

AgentKit 目前在两个云平台上提供：

- [火山引擎（Volcano Engine）](https://www.volcengine.com/)：面向中国大陆的云平台
- [BytePlus](https://www.byteplus.com/)：面向海外市场（含港澳台）的国际云平台

由于两个平台在以下方面存在差异，仓库中现有的示例并不总能直接在 BytePlus 上运行，有时需要较大幅度的修改：

- 产品 / 功能的可用性
- 产品与资源 ID 的命名规范
- API Endpoint 地址
- 支持的 Region

因此本目录下的每个示例都针对 BytePlus 平台进行了适配与验证。

This directory contains a set of AgentKit examples adapted for and tested against **BytePlus**, ByteDance's international cloud platform. The existing samples in this repository target Volcano Engine and do not always work on BytePlus without changes, due to differences in product availability, resource ID naming conventions, API endpoints, and supported regions. Every example here has been verified to run on BytePlus.

## 示例列表 / Included Examples

| 目录 / Subfolder | Agent 名称 | 说明 / Summary |
|------|------------|---------|
| `ad_video_gen` | `ad_video_gen` | 单智能体营销视频生成器：根据商品信息生成 9:16 竖屏短视频。Single-agent marketing video generator: turns product info into a 9:16 short video via a storyboard reference image. |
| `ad_video_gen_seq` | `ad_video_gen_seq` | 顺序多智能体流水线：规划、生成、评估并拼接营销分镜视频。Sequential multi-agent pipeline that plans, generates, evaluates, and stitches marketing shot videos. |
| `comic_drama_gen` | `comic_drama_master` | 将一个故事创意生成完整的漫剧视频：从剧本到分镜再到合成成片。Turns a story idea into a complete comic drama video, from screenplay to storyboard to merged final video. |
| `coding_coach_harness` | `code-coach` | 无代码 **AgentKit Harness** 示例：完全通过 `harness.yaml` + Skill Hub 技能定义的编程练习教练，在 CodeEnv 沙箱中运行学员代码并评分。No-code AgentKit Harness sample defined entirely in `harness.yaml` + a Skill Hub skill, which runs trainee submissions against hidden tests in a CodeEnv sandbox and scores them. |
| `sandbox_demo` | `sandbox_web_coder` | 展示 AgentKit AIO Sandbox 的云端编程智能体：在沙箱内编写并测试 Web 项目，最终通过 TOS 下载链接交付代码。Cloud coding agent showcasing the AgentKit AIO Sandbox: writes and tests web projects entirely inside the sandbox, then delivers the code as a TOS download link. |
| `video_gen` | `storybook_illustrator` | 将儿童故事生成 3D 卡通绘本插画，并合成分镜视频。Turns children's stories into 3D cartoon storybook illustrations and a merged storyboard video. |

## 维护 / Maintenance

本目录由 BytePlus 侧维护，会随 BytePlus 平台能力的更新持续测试与修订。使用示例前请阅读各子目录中的 README 与 `.env.example`。

This directory is maintained on the BytePlus side and is continuously tested and updated as BytePlus platform capabilities evolve. Please read each example's README and `.env.example` before use.
