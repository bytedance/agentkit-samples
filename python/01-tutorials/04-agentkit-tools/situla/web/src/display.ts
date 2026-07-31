import type { ThreadSummary } from "./types";

export function shortId(value: string): string {
  return value.length > 13 ? `${value.slice(0, 8)}…${value.slice(-4)}` : value;
}

export function formatInstanceTime(value?: string): string {
  if (!value) return "未知时间";
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? value
    : new Intl.DateTimeFormat("zh-CN", { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" }).format(date);
}

export function threadTitle(thread: ThreadSummary): string {
  const value = thread.name || thread.preview.trim().split("\n", 1)[0] || "未命名对话";
  return value.length > 30 ? `${value.slice(0, 30)}…` : value;
}

export function relativeThreadTime(timestampSeconds: number): string {
  if (!timestampSeconds) return "未知时间";
  const seconds = Math.max(Math.floor(Date.now() / 1_000) - timestampSeconds, 0);
  if (seconds < 60) return "刚刚";
  if (seconds < 3_600) return `${Math.floor(seconds / 60)} 分钟前`;
  if (seconds < 86_400) return `${Math.floor(seconds / 3_600)} 小时前`;
  if (seconds < 604_800) return `${Math.floor(seconds / 86_400)} 天前`;
  return new Intl.DateTimeFormat("zh-CN", { month: "short", day: "numeric" }).format(timestampSeconds * 1_000);
}

export function formatTime(timestamp: number): string {
  return new Intl.DateTimeFormat("zh-CN", { hour: "2-digit", minute: "2-digit" }).format(timestamp);
}

export function messageOf(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}

export function formatApprovalValue(value: unknown): string {
  try {
    const text = JSON.stringify(value);
    return text.length > 800 ? `${text.slice(0, 800)}…` : text;
  } catch {
    return String(value);
  }
}
