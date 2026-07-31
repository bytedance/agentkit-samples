#!/usr/bin/env -S node --disable-warning=ExperimentalWarning --experimental-strip-types

import { createInterface, type Interface } from "node:readline/promises";
import { stdin, stdout, stderr } from "node:process";
import {
  CodexAppServerClient,
  type ApprovalDecision,
  type ApprovalRequest,
  type ThreadOptions,
} from "./client.ts";
import {
  appServerWebSocketUrl,
  errorText,
  redactSensitiveText,
  redactedUrl,
} from "./protocol.ts";
import { SITULA_VERSION } from "./version.ts";

type ApprovalMode = "ask" | "accept" | "reject";
type ValueOptionTarget =
  | "url"
  | "prompt"
  | "thread"
  | "cwd"
  | "model"
  | "timeoutSeconds"
  | "approval";

interface CliArgs extends ThreadOptions {
  url?: string;
  prompt?: string;
  thread?: string;
  timeoutSeconds: number;
  approval: ApprovalMode;
  verbose: boolean;
  help: boolean;
  version: boolean;
}

function usage(): string {
  return `Situla ${SITULA_VERSION} — chat with Codex in an AgentKit sandbox

Usage:
  situla chat [options]

Options:
  -u, --url <url>          Public sandbox URL (or SANDBOX_URL)
  -p, --prompt <text>      Send one prompt and exit
      --thread <id>        Resume an existing Codex thread
      --cwd <path>         Sandbox working directory for the thread
      --model <model>      Override the sandbox's configured model
      --timeout <seconds>  Request and turn timeout (default: 300)
      --approval <mode>    ask, accept, or reject (default: ask)
  -v, --verbose            Print protocol method names to stderr
  -h, --help               Show this help
      --version            Show the version

Interactive commands:
  /new      Start a new thread
  /thread   Print the current thread id
  /help     Show interactive commands
  /exit     Close the client
`;
}

function parseArgs(argv: string[]): CliArgs {
  const args: CliArgs = {
    timeoutSeconds: 300,
    approval: "ask",
    verbose: false,
    help: false,
    version: false,
  };
  const valueOptions: ReadonlyMap<string, ValueOptionTarget> = new Map([
    ["-u", "url"],
    ["--url", "url"],
    ["-p", "prompt"],
    ["--prompt", "prompt"],
    ["--thread", "thread"],
    ["--cwd", "cwd"],
    ["--model", "model"],
    ["--timeout", "timeoutSeconds"],
    ["--approval", "approval"],
  ]);

  for (let index = 0; index < argv.length; index += 1) {
    const token = argv[index];
    const target = valueOptions.get(token);
    if (target) {
      const value = argv[index + 1];
      if (value === undefined) throw new TypeError(`${token} requires a value`);
      index += 1;
      if (target === "timeoutSeconds") {
        args.timeoutSeconds = Number(value);
      } else if (target === "approval") {
        if (!["ask", "accept", "reject"].includes(value)) {
          throw new TypeError("--approval must be ask, accept, or reject");
        }
        args.approval = value as ApprovalMode;
      } else {
        args[target] = value;
      }
      continue;
    }
    if (token === "-v" || token === "--verbose") args.verbose = true;
    else if (token === "-h" || token === "--help") args.help = true;
    else if (token === "--version") args.version = true;
    else throw new TypeError(`unknown option: ${token}`);
  }

  if (!Number.isFinite(args.timeoutSeconds) || args.timeoutSeconds <= 0) {
    throw new TypeError("--timeout must be greater than zero");
  }
  return args;
}

async function askForApproval(
  terminal: Interface | undefined,
  request: ApprovalRequest,
): Promise<ApprovalDecision> {
  if (!terminal || !stdin.isTTY) {
    stderr.write("\n[approval] no interactive terminal; declined\n");
    return "decline";
  }

  const params = request.params;
  const kind =
    request.method === "item/commandExecution/requestApproval"
      ? "command execution"
      : "file change";
  stderr.write(`\n[approval] ${kind}\n`);
  if (typeof params.reason === "string") stderr.write(`reason: ${params.reason}\n`);
  if (typeof params.command === "string") stderr.write(`command: ${params.command}\n`);
  if (typeof params.cwd === "string") stderr.write(`cwd: ${params.cwd}\n`);
  if (typeof params.grantRoot === "string") stderr.write(`write root: ${params.grantRoot}\n`);

  const answer = (
    await terminal.question("allow? [y] once / [a] session / [n] decline / [c] cancel: ")
  )
    .trim()
    .toLowerCase();
  if (answer === "y" || answer === "yes") return "accept";
  if (answer === "a" || answer === "always") return "acceptForSession";
  if (answer === "c" || answer === "cancel") return "cancel";
  return "decline";
}

function approvalHandler(
  mode: ApprovalMode,
  terminal: Interface | undefined,
): (request: ApprovalRequest) => Promise<ApprovalDecision> {
  return async (request) => {
    if (mode === "accept") return "accept";
    if (mode === "reject") return "decline";
    return askForApproval(terminal, request);
  };
}

async function printTurn(client: CodexAppServerClient, prompt: string): Promise<void> {
  stdout.write("codex> ");
  let streamed = false;
  try {
    const result = await client.runTurn(prompt, (delta) => {
      streamed = true;
      stdout.write(delta);
    });
    if (!streamed && result.text) stdout.write(result.text);
    stdout.write("\n");
    if (result.status === "interrupted") stderr.write("[turn interrupted]\n");
  } catch (error) {
    stdout.write("\n");
    throw error;
  }
}

async function interactiveChat(
  client: CodexAppServerClient,
  terminal: Interface,
  threadOptions: ThreadOptions,
): Promise<void> {
  while (true) {
    let prompt: string;
    try {
      prompt = (await terminal.question("you> ")).trim();
    } catch {
      stdout.write("\n");
      return;
    }
    if (!prompt) continue;
    if (prompt === "/exit" || prompt === "/quit") return;
    if (prompt === "/thread") {
      stdout.write(`${client.threadId ?? "no thread"}\n`);
      continue;
    }
    if (prompt === "/new") {
      const threadId = await client.startThread(threadOptions);
      stderr.write(`[thread] ${threadId}\n`);
      continue;
    }
    if (prompt === "/help") {
      stdout.write("/new  /thread  /help  /exit\n");
      continue;
    }
    try {
      await printTurn(client, prompt);
    } catch (error) {
      stderr.write(`error: ${errorText(error)}\n`);
    }
  }
}

export async function runChat(argv = process.argv.slice(2)): Promise<number> {
  let args: CliArgs;
  try {
    args = parseArgs(argv);
  } catch (error) {
    stderr.write(`error: ${errorText(error)}\n\n${usage()}`);
    return 2;
  }
  if (args.help) {
    stdout.write(usage());
    return 0;
  }
  if (args.version) {
    stdout.write(`${SITULA_VERSION}\n`);
    return 0;
  }

  const sandboxUrl = args.url ?? process.env.SANDBOX_URL;
  if (!sandboxUrl) {
    stderr.write("error: pass --url or set SANDBOX_URL\n");
    return 2;
  }

  const needsTerminal = args.prompt === undefined || args.approval === "ask";
  const terminal = needsTerminal ? createInterface({ input: stdin, output: stdout }) : undefined;
  const timeoutMs = args.timeoutSeconds * 1000;
  let client: CodexAppServerClient | undefined;
  try {
    const websocketUrl = appServerWebSocketUrl(sandboxUrl);
    stderr.write(`connecting to ${redactedUrl(websocketUrl)}\n`);
    client = new CodexAppServerClient(sandboxUrl, {
      requestTimeoutMs: timeoutMs,
      turnTimeoutMs: timeoutMs,
      approvalHandler: approvalHandler(args.approval, terminal),
      ...(args.verbose
        ? {
            onProtocolEvent: (event: { direction: "send" | "receive"; name: string }) =>
              stderr.write(`[${event.direction}] ${event.name}\n`),
          }
        : {}),
    });
    await client.connect();
    const threadOptions = { cwd: args.cwd, model: args.model };
    const threadId = args.thread
      ? await client.resumeThread(args.thread, threadOptions)
      : await client.startThread(threadOptions);
    stderr.write(`[thread] ${threadId}\n`);

    if (args.prompt !== undefined) {
      await printTurn(client, args.prompt);
    } else {
      if (!terminal) throw new Error("interactive terminal is unavailable");
      await interactiveChat(client, terminal, threadOptions);
    }
    return 0;
  } catch (error) {
    const sensitiveUrls = [sandboxUrl];
    try {
      sensitiveUrls.push(appServerWebSocketUrl(sandboxUrl));
    } catch {
      // URL validation errors do not include the unparsed query string.
    }
    const message = redactSensitiveText(errorText(error), sensitiveUrls);
    stderr.write(`error: ${message}\n`);
    return 1;
  } finally {
    client?.close();
    terminal?.close();
  }
}
