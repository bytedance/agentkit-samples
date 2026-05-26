---
name: byted-util-vite-react-tailwind
description: 使用 Vite + React + TailwindCSS v4 + lucide-react 进行前端项目搭建和开发的技能。当用户需要创建前端项目、搭建 React 开发环境、使用 TailwindCSS 进行样式开发时使用此技能。
version: 2.0.0
license: Apache-2.0
metadata:
  display_name: Vite+React+TailwindCSS前端开发工具
  permissions:
    - network
    - file_read
    - file_write
---

# Vite + React + TailwindCSS v4 开发技能

> 基于 Vite + React + TailwindCSS v4 + lucide-react 技术栈的前端项目搭建和开发指南。

## 技术栈

| 技术 | 版本 | 用途 |
|------|------|------|
| Vite | ^5.x 或 ^6.x | 构建工具、开发服务器 |
| React | ^18.x 或 ^19.x | UI 框架 |
| TailwindCSS | ^4.x | 原子化 CSS 框架（Vite 插件模式） |
| @tailwindcss/vite | ^4.x | TailwindCSS Vite 插件 |
| lucide-react | latest | 图标库 |
| TypeScript | ^5.x 或 ^6.x | 类型安全 |

## 项目初始化

### Step 1: 创建 Vite + React 项目

```bash
# 创建项目（使用 React + TypeScript 模板）
npm create vite@latest . -- --template react-ts

# 安装依赖
npm install
```

### Step 2: 安装 TailwindCSS v4

```bash
# 安装 TailwindCSS v4 及 Vite 插件
npm install tailwindcss @tailwindcss/vite
```

> **注意：** v4 不再需要 `postcss`、`autoprefixer`，也不需要运行 `npx tailwindcss init`。

### Step 3: 配置 Vite 插件

在 `vite.config.ts` 中添加 `@tailwindcss/vite` 插件：

**vite.config.ts:**
```ts
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [
    react(),
    tailwindcss(),
  ],
})
```

### Step 4: 清空默认样式并配置 CSS（⚠️ 强制关键步骤）

**必须将 `src/index.css` 和 `src/App.css` 的全部内容清空**，然后在 `src/index.css` 中只写 TailwindCSS 引入（和可选的 `@theme`）：

**src/index.css:**
```css
@import "tailwindcss";
```

**src/App.css:**
```css
/* 清空此文件所有内容，或直接删除此文件 */
```

> **🚨 严格禁止：** 不要在 `index.css` 中写任何 `*`、`body`、`html` 等全局选择器样式！包括但不限于：
> ```css
> /* ❌ 以下全部禁止 */
> * { margin: 0; padding: 0; box-sizing: border-box; }
> body { font-family: ...; -webkit-font-smoothing: antialiased; }
> html { scroll-behavior: smooth; }
> ```
> 这些全局 reset 样式会覆盖 TailwindCSS 的 preflight（内置 reset），导致间距、字体、布局等样式全部异常。TailwindCSS v4 已经内置了完善的 CSS Reset，**不需要也不允许额外添加全局 reset**。
>
> **正确的 `index.css` 只包含**：`@import "tailwindcss"` + 可选的 `@theme` 自定义主题变量。除此之外不写任何 CSS 规则。

> **v4 使用 `@import "tailwindcss"` 替代 v3 的 `@tailwind base; @tailwind components; @tailwind utilities;`。不再需要 `tailwind.config.js` 配置文件。**

### Step 5: 安装 lucide-react 图标库

```bash
npm install lucide-react
```

### Step 6: 安装工具库（如需 cn 工具函数）

```bash
# 用于合并 className 的工具库
npm install clsx tailwind-merge
```

工具函数 `src/utils/cn.ts`：
```typescript
import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}
```

### Step 7: 启动开发服务器

```bash
npm run dev
```

## TypeScript 配置（重要）

### tsconfig.app.json 关键配置

```json
{
  "compilerOptions": {
    "target": "ES2020",
    "module": "ESNext",
    "moduleResolution": "bundler",
    "jsx": "react-jsx",
    "strict": true,
    "verbatimModuleSyntax": false,
    "isolatedModules": true,
    "skipLibCheck": true
  },
  "include": ["src"]
}
```

### ⚠️ 必须注意的 TypeScript 陷阱

1. **`verbatimModuleSyntax` 必须设为 `false`**
   - 设为 `true` 时，`import { MyType } from './types'` 会被保留为运行时导入，但类型在运行时不存在，导致报错
   - 如果设为 `true`，则所有类型导入必须使用 `import type { MyType }` 语法，但这容易遗漏

2. **避免组件名与导入类型同名**
   ```tsx
   // ❌ 错误：TaskStats 类型和函数同名，导致 SyntaxError
   import { TaskStats } from '../../types';
   export default function TaskStats(props: { stats: TaskStats }) { ... }

   // ✅ 正确：重命名类型导入
   import type { TaskStats as TaskStatsData } from '../../types';
   export default function TaskStats(props: { stats: TaskStatsData }) { ... }
   ```

3. **导入路径必须准确**
   - 工具函数 `cn` 定义在 `utils/cn.ts`，不要从 `utils/helpers.ts` 导入
   - 每个工具函数应从其正确的文件路径导入

## 开发规范

### 项目结构

```
src/
├── components/        # 可复用组件
│   ├── ui/           # 基础 UI 组件（Button, Card, Input 等）
│   ├── layout/       # 布局组件（Header, Footer, Sidebar 等）
│   └── features/     # 业务功能组件
├── pages/            # 页面组件
├── hooks/            # 自定义 Hooks
├── utils/            # 工具函数
│   ├── cn.ts         # className 合并工具（clsx + tailwind-merge）
│   └── helpers.ts    # 业务工具函数
├── types/            # TypeScript 类型定义
├── mock/             # Mock 数据
│   └── data.ts       # Mock API 数据
├── assets/           # 静态资源
├── App.tsx           # 根组件
├── main.tsx          # 入口文件
└── index.css         # 全局样式（@import "tailwindcss"）
```

### 组件开发规范

```tsx
import { useState } from 'react';
import { Search, Menu, X } from 'lucide-react';

interface HeaderProps {
  title: string;
  onMenuToggle?: () => void;
}

export function Header({ title, onMenuToggle }: HeaderProps) {
  const [isOpen, setIsOpen] = useState(false);

  return (
    <header className="flex items-center justify-between px-6 py-4 bg-white shadow-sm">
      <h1 className="text-xl font-bold text-gray-900">{title}</h1>
      <div className="flex items-center gap-3">
        <Search className="w-5 h-5 text-gray-500" />
        <button
          onClick={() => {
            setIsOpen(!isOpen);
            onMenuToggle?.();
          }}
          className="p-2 rounded-lg hover:bg-gray-100 transition-colors"
        >
          {isOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
        </button>
      </div>
    </header>
  );
}
```

### 本地 Mock 数据

创建 `src/mock/data.ts` 来模拟 API 数据：

```typescript
// src/mock/data.ts
export const mockUsers = [
  { id: 1, name: '张三', email: 'zhangsan@example.com', avatar: '' },
  { id: 2, name: '李四', email: 'lisi@example.com', avatar: '' },
];

// Mock API 函数
export async function fetchMockData<T>(data: T, delay = 500): Promise<T> {
  return new Promise((resolve) => setTimeout(() => resolve(data), delay));
}
```

### TailwindCSS 常用模式

```tsx
{/* 响应式布局 */}
<div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
  {/* 卡片 */}
  <div className="bg-white rounded-xl shadow-md p-6 hover:shadow-lg transition-shadow">
    <h3 className="text-lg font-semibold text-gray-900">标题</h3>
    <p className="mt-2 text-gray-600">描述文字</p>
  </div>
</div>

{/* 按钮样式 */}
<button className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 active:bg-blue-800 transition-colors font-medium">
  主按钮
</button>

{/* 输入框 */}
<input
  type="text"
  placeholder="请输入..."
  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none"
/>
```

### 图标使用

```tsx
import {
  Home, Settings, User, Bell, Search,
  ChevronRight, ChevronDown, Plus, Trash2, Edit,
  Check, X, AlertCircle, Info, Loader2
} from 'lucide-react';

// 使用图标
<Home className="w-5 h-5 text-gray-600" />
<Loader2 className="w-5 h-5 animate-spin" />  {/* 加载动画 */}
```

## 自测验证

开发完成后，**必须**启动开发服务器并使用 agent-browser 进行自测：

```bash
# 1. 启动开发服务器（后台运行）
npm run dev &

# 2. 等待服务器就绪后，使用 agent-browser 打开页面
agent-browser open http://localhost:5173

# 3. 截取页面快照，检查元素是否正常渲染
agent-browser snapshot -i

# 4. 截图保存，供 QA 参考
agent-browser screenshot --full screenshot.png

# 5. 检查控制台是否有错误
agent-browser eval 'JSON.stringify(window.__errors || "no errors captured")'

# 6. 验证 TailwindCSS 样式是否生效
#    通过 getComputedStyle 检测常见 Tailwind class 是否正确应用
agent-browser eval 'JSON.stringify((() => {
  const checks = [];
  const q = (sel) => document.querySelector(sel);
  const cs = (el) => el ? getComputedStyle(el) : null;

  const flexEl = q(".flex");
  if (flexEl) checks.push({ class: "flex", display: cs(flexEl).display, pass: cs(flexEl).display === "flex" });

  const gridEl = q(".grid");
  if (gridEl) checks.push({ class: "grid", display: cs(gridEl).display, pass: cs(gridEl).display === "grid" });

  const bgEl = q("[class*=\"bg-\"]");
  if (bgEl) checks.push({ class: bgEl.className.match(/bg-\S+/)?.[0], bg: cs(bgEl).backgroundColor, pass: cs(bgEl).backgroundColor !== "rgba(0, 0, 0, 0)" });

  const roundedEl = q("[class*=\"rounded\"]");
  if (roundedEl) checks.push({ class: "rounded", borderRadius: cs(roundedEl).borderRadius, pass: cs(roundedEl).borderRadius !== "0px" });

  const paddingEl = q("[class*=\"p-\"], [class*=\"px-\"], [class*=\"py-\"]");
  if (paddingEl) checks.push({ class: paddingEl.className.match(/p[xy]?-\S+/)?.[0], padding: cs(paddingEl).padding, pass: parseFloat(cs(paddingEl).paddingTop) > 0 || parseFloat(cs(paddingEl).paddingLeft) > 0 });

  const allPass = checks.length > 0 && checks.every(c => c.pass);
  return { tailwindActive: allPass, checksRun: checks.length, details: checks };
})())'

# 7. 验证响应式布局（模拟移动端）
agent-browser close
agent-browser --viewport 375x812 open http://localhost:5173
agent-browser screenshot --full mobile-screenshot.png

# 8. 关闭浏览器
agent-browser close
```

**自测检查清单：**
- [ ] 页面无白屏，所有组件正常渲染
- [ ] 浏览器控制台无 SyntaxError / ReferenceError
- [ ] **TailwindCSS 样式生效**：`tailwindActive: true`，flex/grid/bg/rounded/padding 等 class 的 computedStyle 与预期一致
- [ ] 所有交互功能可用（点击、输入、筛选等）
- [ ] 响应式布局在移动端正常显示
- [ ] 图标正确显示

## 构建与预览

```bash
# 构建生产版本
npm run build

# 本地预览构建结果
npm run preview
```

## 自定义 TailwindCSS 主题

TailwindCSS v4 使用 CSS `@theme` 指令进行主题定制，不再需要 `tailwind.config.js`：

```css
/* src/index.css */
@import "tailwindcss";

@theme {
  --color-primary-50: #f0f9ff;
  --color-primary-500: #3b82f6;
  --color-primary-600: #2563eb;
  --color-primary-700: #1d4ed8;

  --font-sans: 'Inter', system-ui, sans-serif;
  --font-display: 'your-display-font', sans-serif;
}
```

使用自定义主题变量：

```tsx
<div className="bg-primary-500 text-white font-display">品牌区域</div>
<p className="text-primary-700 font-sans">正文内容</p>
```

## 注意事项

- **🚨 `index.css` 中严禁写 `*`、`body`、`html` 等全局选择器样式**，这些会破坏 TailwindCSS 的 preflight reset，导致所有样式异常。`index.css` 只允许 `@import "tailwindcss"` + `@theme`
- 使用 TailwindCSS **v4**（Vite 插件模式），安装 `tailwindcss` 和 `@tailwindcss/vite`
- v4 **不需要** `postcss`、`autoprefixer`、`tailwind.config.js`，也不需要 `npx tailwindcss init`
- CSS 入口使用 `@import "tailwindcss"` 而非 v3 的 `@tailwind` 指令
- 主题定制使用 CSS `@theme` 指令，而非 `tailwind.config.js`
- 所有图标统一使用 lucide-react，不要混用其他图标库
- Mock 数据放在 `src/mock/` 目录，方便后续替换为真实 API
- 组件优先使用函数式组件 + TypeScript
- 遵循 DESIGN.md 中的设计规范进行样式开发
- `verbatimModuleSyntax` 必须设为 `false`，避免类型导入运行时报错
- 使用 `cn()` 工具函数时确保安装了 `clsx` 和 `tailwind-merge`
- 开发完成后必须用 agent-browser 启动页面进行自测验证
