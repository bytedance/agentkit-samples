---
name: byted-util-getdesign-md
description: 从 getdesign.md 下载知名品牌/网站的设计系统文档（DESIGN.md），为前端开发提供风格参考。当需要为项目选择或应用某个品牌的设计系统风格时使用此技能。
version: 1.0.0
license: Apache-2.0
metadata:
  display_name: 品牌设计系统文档下载工具
  permissions:
    - network
    - file_write
---

# getdesign-md Skill

> 从 [getdesign.md](https://getdesign.md) 下载知名品牌/网站的设计系统规范文档（DESIGN.md），让前端开发能够快速复用成熟的设计体系。

## 核心功能

- 根据品牌名称下载对应的 DESIGN.md 设计系统文档
- 涵盖 60+ 知名品牌的设计规范（颜色、字体、间距、组件风格等）
- 下载后的 DESIGN.md 可直接放入项目根目录，指导前端开发

## 安装

```bash
# 无需安装，通过 npx 直接使用
npx getdesign@latest --help
```

## 使用方法

### 搜索可用的设计系统

```bash
# 列出所有可用的设计系统
npx getdesign@latest list
```

### 下载指定品牌的设计系统

```bash
# 下载 Stripe 风格的 DESIGN.md 到当前目录
npx getdesign@latest add stripe

# 下载 Apple 风格
npx getdesign@latest add apple

# 下载 Linear 风格
npx getdesign@latest add linear

# 下载 Nike 风格
npx getdesign@latest add nike

# 下载 Airbnb 风格
npx getdesign@latest add airbnb
```

### 常见品牌关键字

品牌名称全部使用小写，常用的包括：

| 品牌 | 关键字 | 风格描述 |
|------|--------|----------|
| Apple | `apple` | 极简白、SF Pro、影院级画面 |
| Stripe | `stripe` | 紫色渐变、轻盈优雅 |
| Linear | `linear` | 极简精确、紫色强调 |
| Nike | `nike` | 单色UI、大写字体、全幅摄影 |
| Airbnb | `airbnb` | 暖色珊瑚、圆润UI |
| Shopify | `shopify` | 暗色优先、霓虹绿强调 |
| Notion | `notion` | 暖系极简、衬线标题 |
| Figma | `figma` | 多彩活力、专业有趣 |
| Vercel | `vercel` | 黑白精准、Geist字体 |
| Spotify | `spotify` | 深色背景绿色强调、大字体 |
| Tesla | `tesla` | 极度简化、全视口摄影 |
| SpaceX | `spacex` | 黑白对比、全幅图像、未来感 |
| Claude | `claude` | 暖色赤陶、干净编辑布局 |
| Cursor | `cursor` | 暗色界面、渐变强调 |
| Supabase | `supabase` | 暗色翡翠、代码优先 |
| PostHog | `posthog` | 开发者友好暗色UI |

## 工作流程

1. **需求确认**：了解项目目标和用户群体，选择合适的设计风格
2. **下载 DESIGN.md**：使用 `npx getdesign@latest add <brand>` 下载到项目根目录
3. **分析设计规范**：阅读 DESIGN.md 中的颜色系统、字体、间距、组件规范
4. **应用到开发**：将设计规范转化为 TailwindCSS 配置或 CSS 变量，指导前端开发

## 注意事项

- DESIGN.md 文件会下载到当前工作目录
- 如果项目已有 DESIGN.md，会被覆盖
- 可以根据项目需要对下载的设计规范进行定制修改
- 建议将 DESIGN.md 放在项目根目录，方便团队成员参考
