const URL_CANDIDATE = /https?:\/\/[^\s<>"'`]+/giu;
const TRAILING_PUNCTUATION = /[.,;:!?，。；：！？、]+$/u;
const TRAILING_MARKDOWN_EMPHASIS = /(?:\*{1,3}|_{1,3}|~{2})$/u;
const MAX_PREVIEW_URLS = 3;
const MAX_PREVIEW_URL_LENGTH = 2_048;

export function extractSandboxPreviewUrls(content: string): string[] {
  const urls: string[] = [];
  const seen = new Set<string>();
  for (const match of content.matchAll(URL_CANDIDATE)) {
    const normalized = normalizeSandboxPreviewUrl(trimCandidate(match[0]));
    if (!normalized || seen.has(normalized)) continue;
    seen.add(normalized);
    urls.push(normalized);
    if (urls.length >= MAX_PREVIEW_URLS) break;
  }
  return urls;
}

export function normalizeSandboxPreviewUrl(input: string): string | undefined {
  const value = input.trim();
  if (!value || value.length > MAX_PREVIEW_URL_LENGTH) return undefined;
  let url: URL;
  try {
    url = new URL(value);
  } catch {
    return undefined;
  }
  if (!["http:", "https:"].includes(url.protocol) || url.username || url.password) {
    return undefined;
  }
  const hostname = url.hostname.replace(/^\[|\]$/g, "").toLowerCase();
  if (hostname === "0.0.0.0") {
    url.hostname = "127.0.0.1";
  } else if (
    hostname !== "localhost" &&
    hostname !== "::1" &&
    !isIpv4Loopback(hostname)
  ) {
    return undefined;
  }
  return url.toString();
}

function trimCandidate(value: string): string {
  let result = value;
  while (result) {
    const withoutSuffix = result
      .replace(TRAILING_PUNCTUATION, "")
      .replace(TRAILING_MARKDOWN_EMPHASIS, "");
    if (withoutSuffix !== result) {
      result = withoutSuffix;
      continue;
    }
    if (
      (result.endsWith(")") && !result.includes("(")) ||
      (result.endsWith("]") && !result.includes("[")) ||
      (result.endsWith("}") && !result.includes("{"))
    ) {
      result = result.slice(0, -1);
      continue;
    }
    break;
  }
  return result;
}

function isIpv4Loopback(hostname: string): boolean {
  const octets = hostname.split(".");
  return octets.length === 4 &&
    octets[0] === "127" &&
    octets.every((octet) => /^\d{1,3}$/u.test(octet) && Number(octet) <= 255);
}
