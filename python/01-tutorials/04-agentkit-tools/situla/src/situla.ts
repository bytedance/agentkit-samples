#!/usr/bin/env -S node --disable-warning=ExperimentalWarning --experimental-strip-types

import { createInterface } from "node:readline/promises";
import { stdin, stdout, stderr } from "node:process";
import { Writable } from "node:stream";
import {
  loadSitulaConfiguration,
  writeSitulaConfiguration,
} from "./config.ts";
import { errorText } from "./protocol.ts";
import { SITULA_VERSION } from "./version.ts";

function usage(): string {
  return `Situla ${SITULA_VERSION} — AgentKit Codex web client

Usage:
  situla start              Start the local web application
  situla config             Configure runtime options
  situla chat [options]     Open the terminal app-server client
  situla licenses           Print third-party software notices
  situla --version          Print the version
  situla --help             Show this help
`;
}

async function configure(): Promise<void> {
  const loaded = loadSitulaConfiguration();
  const promptOutput = new MaskableOutput();
  const terminal = createInterface({ input: stdin, output: promptOutput, terminal: stdin.isTTY });
  const askValue = (
    label: string,
    current: string,
    sensitive: boolean,
    required = false,
  ) => ask(terminal, promptOutput, label, current, sensitive, required);
  stdout.write(`Situla configuration\nFile:\n  ${loaded.paths.config}\n\n`);
  try {
    const settings = { ...loaded.values };
    settings.VOLCENGINE_REGION = await askValue(
      "Volcengine region",
      settings.VOLCENGINE_REGION,
      false,
    );
    settings.AGENTKIT_HTTP_TIMEOUT = await askValue(
      "HTTP timeout in seconds",
      settings.AGENTKIT_HTTP_TIMEOUT,
      false,
    );
    settings.AGENTKIT_HTTP_RETRIES = await askValue(
      "HTTP retries",
      settings.AGENTKIT_HTTP_RETRIES,
      false,
    );
    settings.SITULA_HOST = await askValue("Listen host", settings.SITULA_HOST, false);
    settings.SITULA_PORT = await askValue("Listen port", settings.SITULA_PORT, false);
    settings.SITULA_ORPHAN_GRACE_MS = await askValue(
      "Session disconnect grace (ms)",
      settings.SITULA_ORPHAN_GRACE_MS,
      false,
    );
    settings.VOLCENGINE_SERVICE = await askValue(
      "Signing service",
      settings.VOLCENGINE_SERVICE,
      false,
    );
    const defaultHost = `agentkit.${settings.VOLCENGINE_REGION}.volcengineapi.com`;
    settings.VOLCENGINE_HOST = await askValue(
      "Control-plane host",
      settings.VOLCENGINE_HOST || defaultHost,
      false,
    );
    writeSitulaConfiguration(settings, loaded.paths);
    stdout.write("\nConfiguration saved.\n");
  } finally {
    terminal.close();
  }
}

async function ask(
  terminal: ReturnType<typeof createInterface>,
  output: MaskableOutput,
  label: string,
  current: string,
  sensitive: boolean,
  required = false,
): Promise<string> {
  while (true) {
    const suffix = current
      ? sensitive
        ? " [configured]"
        : ` [${current}]`
      : "";
    let answer: string;
    if (sensitive && stdin.isTTY) {
      stdout.write(`${label}${suffix}: `);
      output.masked = true;
      try {
        answer = (await terminal.question("")).trim();
      } finally {
        output.masked = false;
        stdout.write("\n");
      }
    } else {
      answer = (await terminal.question(`${label}${suffix}: `)).trim();
    }
    const value = answer === "-" ? "" : answer || current;
    if (!required || value) return value;
    stderr.write(`${label} is required.\n`);
  }
}

class MaskableOutput extends Writable {
  masked = false;
  readonly isTTY = stdout.isTTY;
  readonly columns = stdout.columns;

  override _write(
    chunk: Buffer,
    _encoding: BufferEncoding,
    callback: (error?: Error | null) => void,
  ): void {
    if (!this.masked) stdout.write(chunk);
    callback();
  }
}

async function start(): Promise<number> {
  // Console Login is completed in the local web UI. Persistent runtime options
  // are read by the bridge; SITULA_PRIVATE_TYPE is an explicit compatibility
  // environment variable for legacy Private Tools.
  loadSitulaConfiguration();
  await import("./server.ts");
  return 0;
}

export async function runSitula(argv = process.argv.slice(2)): Promise<number> {
  const [command, ...rest] = argv;
  if (command === "--help" || command === "-h" || command === "help") {
    stdout.write(usage());
    return 0;
  }
  if (command === "--version" || command === "version") {
    stdout.write(`${SITULA_VERSION}\n`);
    return 0;
  }
  if (command === "licenses") {
    if (rest.length) throw new TypeError(`unknown licenses option: ${rest[0]}`);
    const { loadThirdPartyNotices } = await import("./third-party-notices.ts");
    stdout.write(loadThirdPartyNotices());
    return 0;
  }
  if (command === "config") {
    if (rest.length) throw new TypeError(`unknown config option: ${rest[0]}`);
    await configure();
    return 0;
  }
  if (command === "start") {
    if (rest.length) throw new TypeError(`unknown start option: ${rest[0]}`);
    return start();
  }
  if (command === "chat") {
    const { runChat } = await import("./cli.ts");
    return runChat(rest);
  }
  if (!command) {
    stdout.write(usage());
    return 0;
  }
  stderr.write(`error: unknown command ${command}\n\n${usage()}`);
  return 2;
}

runSitula().then(
  (code) => {
    process.exitCode = code;
  },
  (error: unknown) => {
    stderr.write(`error: ${errorText(error)}\n`);
    process.exitCode = 1;
  },
);
