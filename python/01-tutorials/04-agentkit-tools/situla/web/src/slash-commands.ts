import type { ModelSummary } from "./types.js";

export type SlashCommandName =
  | "model"
  | "models"
  | "skills"
  | "new"
  | "resume"
  | "fork"
  | "compact"
  | "archive"
  | "status"
  | "clear"
  | "help";

export interface SlashCommand {
  name: SlashCommandName;
  usage: string;
  description: string;
  keywords: string[];
}

export type SlashMenuItem =
  | { kind: "command"; command: SlashCommand }
  | { kind: "model"; model: ModelSummary };

export const SLASH_COMMANDS: SlashCommand[] = [
  {
    name: "model",
    usage: "/model [model]",
    description: "显示或切换当前对话模型",
    keywords: ["模型", "switch"],
  },
  {
    name: "models",
    usage: "/models",
    description: "列出 app-server 可用模型",
    keywords: ["模型列表", "list"],
  },
  {
    name: "skills",
    usage: "/skills",
    description: "浏览并调用当前工作区可用的 Skill",
    keywords: ["技能", "workflow", "list"],
  },
  {
    name: "new",
    usage: "/new",
    description: "开始一个新对话",
    keywords: ["新建", "对话"],
  },
  {
    name: "resume",
    usage: "/resume [thread]",
    description: "打开历史会话或恢复指定 thread",
    keywords: ["历史", "恢复", "session"],
  },
  {
    name: "fork",
    usage: "/fork",
    description: "从当前上下文分叉一个新对话",
    keywords: ["分叉", "branch"],
  },
  {
    name: "compact",
    usage: "/compact",
    description: "压缩当前对话上下文",
    keywords: ["压缩", "上下文"],
  },
  {
    name: "archive",
    usage: "/archive",
    description: "归档当前对话并新建对话",
    keywords: ["归档", "关闭"],
  },
  {
    name: "status",
    usage: "/status",
    description: "显示当前连接、thread 和模型状态",
    keywords: ["状态", "连接"],
  },
  {
    name: "clear",
    usage: "/clear",
    description: "清空当前视图并开始新对话",
    keywords: ["清空", "重置"],
  },
  {
    name: "help",
    usage: "/help",
    description: "显示 Situla 支持的快捷命令",
    keywords: ["帮助", "命令"],
  },
];

export interface SlashInvocation {
  name: string;
  argument: string;
}

export function parseSlashInvocation(value: string): SlashInvocation | undefined {
  const trimmed = value.trim();
  const match = trimmed.match(/^\/([^\s]+)(?:\s+([\s\S]*))?$/);
  if (!match) return undefined;
  return { name: match[1].toLowerCase(), argument: match[2]?.trim() ?? "" };
}

export function slashMenuItems(
  value: string,
  models: readonly ModelSummary[],
): SlashMenuItem[] {
  if (!value.startsWith("/") || value.includes("\n")) return [];
  const raw = value.slice(1);
  const separator = raw.search(/\s/);
  const commandQuery = (separator < 0 ? raw : raw.slice(0, separator)).toLowerCase();
  const argument = separator < 0 ? "" : raw.slice(separator).trim().toLowerCase();

  if (separator >= 0 && commandQuery === "model") {
    return models
      .filter((model) => modelMatches(model, argument))
      .sort((left, right) => modelScore(left, argument) - modelScore(right, argument))
      .slice(0, 12)
      .map((model) => ({ kind: "model", model }));
  }

  return SLASH_COMMANDS
    .filter((command) => commandMatches(command, commandQuery))
    .sort((left, right) => commandScore(left, commandQuery) - commandScore(right, commandQuery))
    .slice(0, 10)
    .map((command) => ({ kind: "command", command }));
}

function commandMatches(command: SlashCommand, query: string): boolean {
  if (!query) return true;
  return [command.name, command.description, ...command.keywords]
    .some((value) => value.toLowerCase().includes(query));
}

function commandScore(command: SlashCommand, query: string): number {
  if (!query) return SLASH_COMMANDS.indexOf(command);
  if (command.name === query) return 0;
  if (command.name.startsWith(query)) return 1;
  if (command.name.includes(query)) return 2;
  return 3;
}

function modelMatches(model: ModelSummary, query: string): boolean {
  if (!query) return true;
  return `${model.id} ${model.displayName} ${model.description}`.toLowerCase().includes(query);
}

function modelScore(model: ModelSummary, query: string): number {
  if (!query) return model.isDefault ? 0 : 1;
  if (model.id.toLowerCase() === query) return 0;
  if (model.id.toLowerCase().startsWith(query)) return 1;
  if (model.displayName.toLowerCase().startsWith(query)) return 2;
  return 3;
}
