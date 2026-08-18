import type { ReactNode, RefObject, UIEventHandler } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { formatTime } from "../display";
import { extractSandboxPreviewUrls } from "../preview-url";
import { skillDisplayParts } from "../skill-mentions";
import type { ChatMessage, ExecutionStep, SkillSummary } from "../types";
import { AlertIcon, ArrowDownIcon, BrowserIcon, LinkIcon, Logo, SkillIcon, TerminalIcon, UserIcon } from "./ui";

const SUGGESTIONS = [
  {
    icon: "☀",
    title: "制作太阳系运行图",
    description: "创建可交互网页，并启动沙箱内的本地预览服务。",
    prompt: `请直接在沙箱中制作一个可以运行和预览的太阳系运行图网页，具体要求如下：

1. 将成品放在 /home/gem/solar-system，至少创建 index.html；可以按需拆分 style.css 和 script.js，但不要依赖需要联网加载的图片、字体或前端库。
2. 使用深色太空背景，展示太阳、八大行星和清晰可见的运行轨道。行星大小、轨道距离和公转速度可以采用适合屏幕观赏的非真实比例，但不同星体应容易区分。
3. 让行星持续围绕太阳公转，并提供行星名称、暂停/继续和公转速度调节功能；页面应适配常见窗口尺寸，整体视觉完整、动画流畅。
4. 完成后自行检查 HTML、CSS 和 JavaScript 是否能正常加载，修复明显的布局、脚本或资源路径问题。
5. 不要让我直接打开 /home/gem/solar-system/index.html，也不要使用 file://。请在沙箱内选择一个可用端口（优先从 8000 开始），使用 Python 静态服务器在 127.0.0.1 上提供该目录，并让服务在本轮任务结束后继续运行。可以采用类似下面的方式：
   nohup python3 -m http.server 8000 --bind 127.0.0.1 --directory /home/gem/solar-system >/tmp/solar-system-http.log 2>&1 &
6. 启动后使用 curl 验证 index.html 能通过 HTTP 成功访问。最后明确告诉我实际端口，以及应该在“沙箱浏览器”中打开的完整地址，例如 http://127.0.0.1:8000/index.html。

请完成创建、验证和启动预览的全过程，不要只给我示例代码或操作说明。`,
  },
  {
    icon: "◇",
    title: "生成沙箱体检报告",
    description: "采集真实环境信息，生成可视化网页报告。",
    prompt: `请直接检查当前沙箱，并制作一份可以在浏览器中查看的沙箱环境体检报告，具体要求如下：

1. 只使用安全的只读命令采集真实信息，例如操作系统与内核、CPU、内存、磁盘、运行时长、Python 和 Node.js 版本，以及 /home/gem 下一级目录概况。某项工具不存在时如实标记为“不可用”，不要编造数据。
2. 不要读取或展示环境变量、凭据、token、SSH 配置、浏览器数据、.env 文件或其他可能包含秘密的文件内容；报告中也不要包含完整进程命令行等可能泄露敏感参数的信息。
3. 将报告制作在 /home/gem/sandbox-report/index.html。使用卡片、表格和适当的进度条展示采集结果，注明生成时间和数据含义；对插入 HTML 的命令输出进行正确转义。
4. 报告必须完全自包含，不依赖外部 CDN、字体、图片或网络接口，并适配常见窗口尺寸。完成后核对网页显示的数据与实际命令输出是否一致。
5. 不要让我直接打开 /home/gem/sandbox-report/index.html，也不要使用 file://。请在沙箱内选择一个可用端口（优先从 8001 开始），使用 Python 静态服务器在 127.0.0.1 上提供该目录，并让服务在本轮任务结束后继续运行。可以采用类似下面的方式：
   nohup python3 -m http.server 8001 --bind 127.0.0.1 --directory /home/gem/sandbox-report >/tmp/sandbox-report-http.log 2>&1 &
6. 启动后使用 curl 验证 index.html 能通过 HTTP 成功访问。最后总结发现的环境信息，并明确告诉我实际端口及“沙箱浏览器”应打开的完整地址，例如 http://127.0.0.1:8001/index.html。

请完成信息采集、报告生成、验证和启动预览的全过程，不要只给我命令或操作说明。`,
  },
  {
    icon: "GH",
    title: "制作 GitHub 项目简历",
    description: "读取公开项目经历，生成个人简历并启动预览。",
    prompt: `请在当前沙箱内制作一份基于本人 GitHub 公开资料和项目经历的个人简历网页，具体要求如下：

1. 首先查找沙箱中已安装的 GitHub Skill，完整阅读其 SKILL.md，并严格按照该 Skill 的流程操作。检查状态，辅助用户完成登录。
2. 如果用户没有登录，请按照skill规范，提供给用户登录授权码以及URL。
3. 当用户确认登录后，使用该 Skill 读取用户的公开 GitHub 资料和项目经历，包括但不限于：用户名、头像、简介、仓库列表、贡献记录等。不要读取任何私有信息或敏感数据。
4. 将读取到的资料整理成一份简历网页，放在 /home/gem/github-resume/index.html。网页应包含个人信息、项目经历、技能标签和联系方式等内容，并使用卡片、表格或列表进行清晰展示。网页必须完全自包含，不依赖外部 CDN、字体、图片或网络接口，并适配常见窗口尺寸。
5. 完成后核对网页显示的数据与实际 GitHub 资料是否一致。
6. 不要让我直接打开 /home/gem/github-resume/index.html，也不要使用 file://。请在沙箱内选择一个可用端口（优先从 8002 开始），使用 Python 静态服务器在 127.0.0.1 上提供该目录，并让服务在本轮任务结束后继续运行。可以采用类似下面的方式：
  nohup python3 -m http.server 8002 --bind 127.0.0.1 --directory /home/gem/github-resume >/tmp/github-resume-http.log 2>&1 &
7. 启动后使用 curl 验证 index.html 能通过 HTTP 成功访问。最后总结发现的环境信息，并明确告诉我实际端口及“沙箱浏览器”应打开的完整地址，例如 http://127.0.0.1:8002/index.html。

除等待我完成 GitHub 官方授权外，请完成资料读取、简历生成、验证和启动预览的全过程，不要只给我示例代码或操作说明。`,
  },
];

interface ChatPanelProps {
  messages: ChatMessage[];
  skills: SkillSummary[];
  connected: boolean;
  scrollRef: RefObject<HTMLDivElement | null>;
  onScroll: UIEventHandler<HTMLDivElement>;
  onSuggestion: (value: string) => void;
  onConnect: () => void;
  showJumpToLatest: boolean;
  onJumpToLatest: () => void;
  error?: string;
  onDismissError: () => void;
  onPreviewUrl: (url: string) => void;
  composer: ReactNode;
}

export function ChatPanel({
  messages,
  skills,
  connected,
  scrollRef,
  onScroll,
  onSuggestion,
  onConnect,
  showJumpToLatest,
  onJumpToLatest,
  error,
  onDismissError,
  onPreviewUrl,
  composer,
}: ChatPanelProps) {
  return (
    <div className="content-grid">
      <section className="chat-pane">
        <div className="message-scroll" ref={scrollRef} onScroll={onScroll}>
          {messages.length === 0 ? (
            <EmptyState connected={connected} onSuggestion={onSuggestion} onConnect={onConnect} />
          ) : (
            <div className="messages">
              {messages.map((message) => (
                <Message
                  key={message.id}
                  message={message}
                  skills={skills}
                  previewEnabled={connected}
                  onPreviewUrl={onPreviewUrl}
                />
              ))}
            </div>
          )}
        </div>
        {showJumpToLatest && messages.length > 0 && (
          <button className="jump-to-latest" onClick={onJumpToLatest}><ArrowDownIcon />回到最新消息</button>
        )}
        {error && (
          <div className="error-banner" role="alert">
            <AlertIcon />
            <span>{error}</span>
            <button onClick={onDismissError}>关闭</button>
          </div>
        )}
        {composer}
      </section>
    </div>
  );
}

function EmptyState({ connected, onSuggestion, onConnect }: { connected: boolean; onSuggestion: (value: string) => void; onConnect: () => void }) {
  return (
    <div className="empty-state">
      <div className="hero-mark"><Logo large /></div>
      <div className="hero-kicker">REMOTE CODEX · LOCAL CONTROL</div>
      <h1>{connected ? "今天想构建什么？" : "连接你的 Codex 沙箱"}</h1>
      <p>{connected ? "消息通过本地 bridge 流向沙箱；代码、命令和上下文都留在隔离环境中。" : "从 AgentKit Tool 选择或创建一个 Session 实例，Situla 会连接其中的 Codex app-server。"}</p>
      {connected ? (
        <div className="suggestion-grid">
          {SUGGESTIONS.map((suggestion) => (
            <button key={suggestion.title} onClick={() => onSuggestion(suggestion.prompt)}>
              <span>{suggestion.icon}</span><strong>{suggestion.title}</strong><small>{suggestion.description}</small>
            </button>
          ))}
        </div>
      ) : (
        <button className="primary hero-connect" onClick={onConnect}><LinkIcon />配置沙箱连接</button>
      )}
    </div>
  );
}

function Message({
  message,
  skills,
  previewEnabled,
  onPreviewUrl,
}: {
  message: ChatMessage;
  skills: readonly SkillSummary[];
  previewEnabled: boolean;
  onPreviewUrl: (url: string) => void;
}) {
  const author = message.role === "user" ? "你" : message.role === "system" ? "Situla" : "Codex";
  const userDisplay = message.role === "user" && !message.skillNames?.length
    ? skillDisplayParts(message.content, [])
    : {
        content: message.content,
        skillNames: message.skillNames ?? [],
      };
  const previewUrls = message.role === "assistant" && message.state === "complete"
    ? extractSandboxPreviewUrls(message.content)
    : [];
  return (
    <article className={`message ${message.role} ${message.state}`}>
      <div className="message-avatar">{message.role === "user" ? <UserIcon /> : message.role === "system" ? <TerminalIcon /> : <Logo compact />}</div>
      <div className="message-body">
        <div className="message-meta"><strong>{author}</strong><time>{formatTime(message.timestamp)}</time>{message.state === "streaming" && <span className="thinking-label">正在生成</span>}</div>
        {message.role === "assistant" && message.execution && message.execution.length > 0 && (
          <ExecutionPanel steps={message.execution} streaming={message.state === "streaming"} />
        )}
        {message.role === "user" && userDisplay.skillNames.length > 0 && (
          <div className="message-skills">
            {userDisplay.skillNames.map((name) => (
              <SkillDisclosure
                key={name}
                name={name}
                description={skills.find((skill) => skill.name === name)?.description}
              />
            ))}
          </div>
        )}
        <RichText
          content={message.role === "user" ? userDisplay.content : message.content}
          streaming={message.state === "streaming"}
          markdown={message.role !== "user"}
        />
        {previewUrls.length > 0 && (
          <div className="preview-cards">
            {previewUrls.map((url) => (
              <div className="preview-card" key={url}>
                <span className="preview-card-icon"><BrowserIcon /></span>
                <span className="preview-card-copy">
                  <strong>网页产物</strong>
                  <code title={url}>{displayPreviewUrl(url)}</code>
                </span>
                <button onClick={() => onPreviewUrl(url)} disabled={!previewEnabled}>
                  {previewEnabled ? "打开预览" : "连接后预览"}
                </button>
              </div>
            ))}
          </div>
        )}
        {message.role === "assistant" && message.state === "complete" && message.tokenUsage && (
          <div
            className="message-usage"
            title={usageTitle(message.tokenUsage.turn)}
            aria-label={usageTitle(message.tokenUsage.turn)}
          >
            <strong>Total {formatTokens(message.tokenUsage.turn.totalTokens)}</strong>
            <span>Input {formatTokens(message.tokenUsage.turn.inputTokens)}</span>
            {message.tokenUsage.turn.cachedInputTokens > 0 && (
              <span>Cached input {formatTokens(message.tokenUsage.turn.cachedInputTokens)}</span>
            )}
            <span>Output {formatTokens(message.tokenUsage.turn.outputTokens)}</span>
            {message.tokenUsage.turn.reasoningOutputTokens > 0 && (
              <span>Reasoning output {formatTokens(message.tokenUsage.turn.reasoningOutputTokens)}</span>
            )}
          </div>
        )}
      </div>
    </article>
  );
}

function displayPreviewUrl(value: string): string {
  const url = new URL(value);
  return `${url.host}${url.pathname}${url.search}${url.hash}`;
}

function SkillDisclosure({
  name,
  description,
}: {
  name: string;
  description?: string;
}) {
  return (
    <details className="message-skill">
      <summary>
        <SkillIcon />
        <strong>{name}</strong>
        <span className="message-skill-kind">Skill</span>
        <span className="message-skill-chevron" />
      </summary>
      <dl>
        <div><dt>名称</dt><dd>{name}</dd></div>
        <div><dt>描述</dt><dd>{description || "当前 Skill 未提供描述。"}</dd></div>
      </dl>
    </details>
  );
}

function ExecutionPanel({ steps, streaming }: { steps: ExecutionStep[]; streaming: boolean }) {
  const running = streaming ? [...steps].reverse().find((step) => step.status === "running") : undefined;
  const toolCount = steps.filter((step) =>
    ["command", "file", "mcp", "dynamic", "web", "collab", "image"].includes(step.kind)
  ).length;
  const failed = steps.some((step) => step.status === "failed");
  const summary = running
    ? running.title
    : `${steps.length} 个步骤${toolCount > 0 ? ` · ${toolCount} 个工具调用` : ""}`;

  return (
    <details className={`execution-panel${running ? " running" : ""}`}>
      <summary>
        <span className={`execution-summary-status${failed ? " failed" : ""}`} aria-hidden="true" />
        <strong>执行过程</strong>
        <span className="execution-summary-text">{summary}</span>
        <span className="execution-chevron" aria-hidden="true" />
      </summary>
      <div className="execution-steps">
        {steps.map((step) => (
          <div className={`execution-step ${step.status}`} key={step.id}>
            <span className="execution-step-status" aria-hidden="true" />
            <div className="execution-step-body">
              <div className="execution-step-heading">
                <span className="execution-kind">{executionKindLabel(step.kind)}</span>
                <strong>{step.title}</strong>
                {step.durationMs !== undefined && (
                  <time>{formatExecutionDuration(step.durationMs)}</time>
                )}
              </div>
              {step.detail && <pre>{step.detail}</pre>}
            </div>
          </div>
        ))}
      </div>
    </details>
  );
}

function executionKindLabel(kind: ExecutionStep["kind"]): string {
  return {
    reasoning: "WORKING",
    command: "COMMAND",
    file: "FILES",
    mcp: "MCP",
    dynamic: "TOOL",
    web: "WEB",
    collab: "AGENT",
    image: "IMAGE",
    plan: "PLAN",
    context: "CONTEXT",
    other: "SYSTEM",
  }[kind];
}

function formatExecutionDuration(durationMs: number): string {
  if (durationMs < 1_000) return `${durationMs} ms`;
  return `${(durationMs / 1_000).toFixed(durationMs < 10_000 ? 1 : 0)} s`;
}

function formatTokens(value: number): string {
  if (value >= 1_000_000) return `${trimDecimal(value / 1_000_000)}m`;
  if (value >= 1_000) return `${trimDecimal(value / 1_000)}k`;
  return value.toLocaleString("zh-CN");
}

function trimDecimal(value: number): string {
  return value.toFixed(value >= 100 ? 0 : 1).replace(/\.0$/, "");
}

function usageTitle(usage: NonNullable<ChatMessage["tokenUsage"]>["turn"]): string {
  return [
    `Total ${usage.totalTokens.toLocaleString("en-US")} tokens`,
    `Input ${usage.inputTokens.toLocaleString("en-US")}`,
    `Cached input ${usage.cachedInputTokens.toLocaleString("en-US")}`,
    `Output ${usage.outputTokens.toLocaleString("en-US")}`,
    `Reasoning output ${usage.reasoningOutputTokens.toLocaleString("en-US")}`,
  ].join(", ");
}

function RichText({
  content,
  streaming,
  markdown,
}: {
  content: string;
  streaming: boolean;
  markdown: boolean;
}) {
  if (!content && streaming) return <div className="thinking"><i /><i /><i /></div>;
  if (!markdown) {
    return (
      <div className="message-content plain">
        {content}
      </div>
    );
  }
  return (
    <div className={`message-content markdown${streaming ? " streaming" : ""}`}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        skipHtml
        components={{
          a: ({ node: _node, ...props }) => (
            <a {...props} target="_blank" rel="noopener noreferrer" />
          ),
          img: ({ node: _node, src, alt }) => src ? (
            <a
              className="markdown-image-link"
              href={src}
              target="_blank"
              rel="noopener noreferrer"
            >
              Image: {alt || src}
            </a>
          ) : null,
        }}
      >
        {content}
      </ReactMarkdown>
      {streaming && <span className="stream-caret" />}
    </div>
  );
}
