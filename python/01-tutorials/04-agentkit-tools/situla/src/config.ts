import { randomBytes } from "node:crypto";
import {
  chmodSync,
  mkdirSync,
  readFileSync,
  renameSync,
  writeFileSync,
} from "node:fs";
import { homedir } from "node:os";
import { dirname, isAbsolute, join } from "node:path";

export const CONFIG_KEYS = [
  "VOLCENGINE_REGION",
  "VOLCENGINE_SERVICE",
  "VOLCENGINE_HOST",
  "AGENTKIT_HTTP_TIMEOUT",
  "AGENTKIT_HTTP_RETRIES",
  "SITULA_HOST",
  "SITULA_PORT",
  "SITULA_ORPHAN_GRACE_MS",
] as const;

export type ConfigKey = (typeof CONFIG_KEYS)[number];
export type SitulaSettings = Record<ConfigKey, string>;

const LEGACY_CONFIG_KEYS = ["TOOL_TYPE"] as const;
const ACCEPTED_CONFIG_KEYS = [...CONFIG_KEYS, ...LEGACY_CONFIG_KEYS] as const;

export interface SitulaConfigPaths {
  directory: string;
  config: string;
}

export interface LoadedSitulaConfiguration {
  values: SitulaSettings;
  paths: SitulaConfigPaths;
}

const STATIC_DEFAULTS: Partial<SitulaSettings> = {
  VOLCENGINE_REGION: "cn-beijing",
  VOLCENGINE_SERVICE: "agentkit",
  AGENTKIT_HTTP_TIMEOUT: "30",
  AGENTKIT_HTTP_RETRIES: "2",
  SITULA_HOST: "127.0.0.1",
  SITULA_PORT: "8787",
  SITULA_ORPHAN_GRACE_MS: "60000",
};

export function situlaConfigPaths(env: NodeJS.ProcessEnv = process.env): SitulaConfigPaths {
  const xdgDirectory = env.XDG_CONFIG_HOME?.trim();
  const baseDirectory = xdgDirectory
    ? isAbsolute(xdgDirectory)
      ? xdgDirectory
      : join(homedir(), xdgDirectory)
    : join(homedir(), ".config");
  const directory = join(baseDirectory, "situla");
  return {
    directory,
    config: join(directory, "config.json"),
  };
}

export function loadSitulaConfiguration(
  env: NodeJS.ProcessEnv = process.env,
): LoadedSitulaConfiguration {
  const paths = situlaConfigPaths(env);
  const configuredOptions = readSettingsFile(paths.config, ACCEPTED_CONFIG_KEYS);
  const values = {} as SitulaSettings;

  for (const key of CONFIG_KEYS) {
    if (Object.hasOwn(configuredOptions, key)) {
      values[key] = configuredOptions[key] ?? "";
      continue;
    }
    values[key] = STATIC_DEFAULTS[key] ?? "";
  }
  if (!values.VOLCENGINE_HOST.trim()) {
    values.VOLCENGINE_HOST = `agentkit.${values.VOLCENGINE_REGION.trim() || "cn-beijing"}.volcengineapi.com`;
  }
  validateSitulaSettings(values);
  return { values, paths };
}

export function validateSitulaSettings(settings: SitulaSettings): void {
  requireText(settings.VOLCENGINE_REGION, "VOLCENGINE_REGION");
  const service = requireText(settings.VOLCENGINE_SERVICE, "VOLCENGINE_SERVICE");
  if (!/^[a-z0-9][a-z0-9_-]{0,63}$/i.test(service)) {
    throw new TypeError("VOLCENGINE_SERVICE contains invalid characters");
  }
  validateHost(settings.VOLCENGINE_HOST);
  positiveNumber(settings.AGENTKIT_HTTP_TIMEOUT, "AGENTKIT_HTTP_TIMEOUT");
  nonNegativeInteger(settings.AGENTKIT_HTTP_RETRIES, "AGENTKIT_HTTP_RETRIES");
  const port = nonNegativeInteger(settings.SITULA_PORT, "SITULA_PORT");
  if (port > 65_535) throw new TypeError("SITULA_PORT must be between 0 and 65535");
  positiveNumber(settings.SITULA_ORPHAN_GRACE_MS, "SITULA_ORPHAN_GRACE_MS");
}

export function writeSitulaConfiguration(settings: SitulaSettings, paths: SitulaConfigPaths): void {
  validateSitulaSettings(settings);
  mkdirSync(paths.directory, { recursive: true, mode: 0o700 });
  chmodSync(paths.directory, 0o700);
  writeJsonAtomic(paths.config, settings);
}

function readSettingsFile<Key extends string>(
  path: string,
  allowedKeys: readonly Key[],
): Partial<Record<Key, string>> {
  let text: string;
  try {
    text = readFileSync(path, "utf8");
  } catch (error) {
    if (isNodeError(error) && error.code === "ENOENT") return {};
    throw new Error(`cannot read ${path}: ${errorMessage(error)}`, { cause: error });
  }
  let value: unknown;
  try {
    value = JSON.parse(text);
  } catch (error) {
    throw new Error(`${path} must contain valid JSON`, { cause: error });
  }
  if (!isRecord(value)) throw new TypeError(`${path} must contain a JSON object`);
  const allowed = new Set<string>(allowedKeys);
  const result: Partial<Record<Key, string>> = {};
  for (const [key, raw] of Object.entries(value)) {
    if (!allowed.has(key)) throw new TypeError(`${path} contains unknown setting ${key}`);
    if (typeof raw !== "string" && typeof raw !== "number") {
      throw new TypeError(`${path} setting ${key} must be a string or number`);
    }
    result[key as Key] = String(raw);
  }
  return result;
}

function writeJsonAtomic(path: string, value: Record<string, string>): void {
  const temporaryPath = join(
    dirname(path),
    `.${path.split("/").at(-1)}.${process.pid}.${randomBytes(6).toString("hex")}.tmp`,
  );
  writeFileSync(temporaryPath, `${JSON.stringify(value, null, 2)}\n`, { mode: 0o600 });
  renameSync(temporaryPath, path);
  chmodSync(path, 0o600);
}

function validateHost(value: string): void {
  const host = requireText(value, "VOLCENGINE_HOST");
  if (!/^[a-z0-9.-]+(?::\d{1,5})?$/i.test(host)) {
    throw new TypeError("VOLCENGINE_HOST must be a hostname, optionally followed by a port");
  }
  try {
    const parsed = new URL(`https://${host}`);
    if (!parsed.hostname || parsed.pathname !== "/") throw new Error("invalid host");
  } catch (error) {
    throw new TypeError("VOLCENGINE_HOST must be a valid hostname", { cause: error });
  }
}

function requireText(value: string, name: string): string {
  const normalized = value.trim();
  if (!normalized) throw new TypeError(`${name} must not be empty`);
  return normalized;
}

function positiveNumber(value: string, name: string): number {
  const parsed = Number(value);
  if (!Number.isFinite(parsed) || parsed <= 0) throw new TypeError(`${name} must be greater than zero`);
  return parsed;
}

function nonNegativeInteger(value: string, name: string): number {
  const parsed = Number(value);
  if (!Number.isSafeInteger(parsed) || parsed < 0) {
    throw new TypeError(`${name} must be a non-negative integer`);
  }
  return parsed;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isNodeError(value: unknown): value is NodeJS.ErrnoException {
  return value instanceof Error && "code" in value;
}

function errorMessage(value: unknown): string {
  return value instanceof Error ? value.message : String(value);
}
