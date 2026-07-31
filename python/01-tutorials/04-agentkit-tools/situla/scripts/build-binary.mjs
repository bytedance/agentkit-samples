#!/usr/bin/env node

import { createHash } from "node:crypto";
import { execFileSync, execSync } from "node:child_process";
import {
  chmodSync,
  copyFileSync,
  mkdirSync,
  readFileSync,
  readdirSync,
  renameSync,
  writeFileSync,
} from "node:fs";
import { basename, dirname, extname, join, relative, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { build as esbuild } from "esbuild";
import { build as viteBuild } from "vite";
import {
  assertReleaseNodeVersion,
  generateThirdPartyNotices,
} from "./generate-third-party-notices.mjs";

const nodeVersion = process.versions.node;
const [major] = nodeVersion.split(".").map(Number);
const useBuildSea = major >= 25;

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const workDirectory = join(root, ".binary");
const webDirectory = join(root, "dist", "web");
const generatedAssets = join(workDirectory, "web-assets.ts");
const generatedNotices = join(workDirectory, "third-party-notices.ts");
const bundle = join(workDirectory, "situla.cjs");
const blob = join(workDirectory, "situla.blob");
const platform = platformName(process.platform);
const architecture = architectureName(process.arch);
const packageMetadata = JSON.parse(readFileSync(join(root, "package.json"), "utf8"));
const version = String(packageMetadata.version);
if (!/^\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?$/.test(version)) {
  throw new Error(`package.json contains an invalid version: ${version}`);
}
const runtimeVersion = readFileSync(join(root, "src", "version.ts"), "utf8")
  .match(/SITULA_VERSION\s*=\s*"([^"]+)"/)?.[1];
if (runtimeVersion !== version) {
  throw new Error(`version mismatch: package.json=${version}, src/version.ts=${runtimeVersion ?? "missing"}`);
}
const executableName = `situla-v${version}-${platform}-${architecture}${process.platform === "win32" ? ".exe" : ""}`;
const executable = join(root, "dist", executableName);
const stagedExecutable = join(workDirectory, executableName);
const seaBundle = relative(root, bundle);
const seaBlob = relative(root, blob);
const seaExecutable = relative(root, stagedExecutable);

mkdirSync(workDirectory, { recursive: true });
mkdirSync(dirname(executable), { recursive: true });

assertReleaseNodeVersion();
const notices = generateThirdPartyNotices();
writeFileSync(
  generatedNotices,
  `export function loadThirdPartyNotices() {\n  return ${JSON.stringify(notices.output)};\n}\n`,
);

console.log("Building web UI...");
await viteBuild({ configFile: join(root, "vite.config.ts") });
writeFileSync(generatedAssets, generatedWebAssets(webDirectory));

console.log("Bundling Node application...");
await esbuild({
  entryPoints: [join(root, "src", "situla.ts")],
  outfile: bundle,
  bundle: true,
  format: "cjs",
  platform: "node",
  target: "node22",
  minify: true,
  sourcemap: false,
  plugins: [{
    name: "situla-embedded-web-assets",
    setup(build) {
      build.onResolve({ filter: /^\.\/web-assets\.ts$/ }, (args) => {
        if (args.importer.endsWith(join("src", "server.ts"))) return { path: generatedAssets };
        return undefined;
      });
      build.onResolve({ filter: /^\.\/third-party-notices\.ts$/ }, (args) => {
        if (args.importer.endsWith(join("src", "situla.ts"))) return { path: generatedNotices };
        return undefined;
      });
    },
  }],
});

console.log(`Creating ${executableName}...`);

if (useBuildSea) {
  const seaConfig = join(workDirectory, "sea-config.json");
  writeFileSync(seaConfig, `${JSON.stringify({
    main: seaBundle,
    output: seaExecutable,
    disableExperimentalSEAWarning: true,
    useSnapshot: false,
    useCodeCache: false,
  }, null, 2)}\n`);

  execFileSync(process.execPath, ["--build-sea", seaConfig], {
    cwd: root,
    stdio: "inherit",
  });
  chmodSync(stagedExecutable, 0o755);
} else {
  const seaConfig = join(workDirectory, "sea-config.json");
  writeFileSync(seaConfig, `${JSON.stringify({
    main: seaBundle,
    output: seaBlob,
    disableExperimentalSEAWarning: true,
    useSnapshot: false,
    useCodeCache: false,
  }, null, 2)}\n`);

  execFileSync(process.execPath, ["--experimental-sea-config", seaConfig], {
    cwd: root,
    stdio: "inherit",
  });
  copyFileSync(process.execPath, stagedExecutable);
  chmodSync(stagedExecutable, 0o755);
  if (process.platform === "darwin") {
    execFileSync("codesign", ["--remove-signature", stagedExecutable], { stdio: "inherit" });
  }
  const postjectArgs = [
    join(root, "node_modules", "postject", "dist", "cli.js"),
    stagedExecutable,
    "NODE_SEA_BLOB",
    blob,
    "--sentinel-fuse",
    "NODE_SEA_FUSE_fce680ab2cc467b6e072b8b5df1996b2",
  ];
  if (process.platform === "darwin") {
    postjectArgs.push("--macho-segment-name", "NODE_SEA");
  }
  execFileSync(
    process.execPath,
    postjectArgs,
    { cwd: root, stdio: "inherit" },
  );
  if (process.platform === "darwin") {
    execFileSync("codesign", ["--sign", "-", stagedExecutable], { stdio: "inherit" });
  }
}

renameSync(stagedExecutable, executable);
const checksum = createHash("sha256").update(readFileSync(executable)).digest("hex");
writeFileSync(`${executable}.sha256`, `${checksum}  ${basename(executable)}\n`);
console.log(`Binary ready: ${relative(root, executable)}`);

function generatedWebAssets(directory) {
  const files = walk(directory).sort();
  const entries = files.map((path) => {
    const key = relative(directory, path).split("\\").join("/");
    const encoded = readFileSync(path).toString("base64");
    return `  [${JSON.stringify(key)}, { body: Buffer.from(${JSON.stringify(encoded)}, "base64"), contentType: ${JSON.stringify(contentType(path))} }],`;
  });
  return `export const embeddedWebAssets = new Map([\n${entries.join("\n")}\n]);\n`;
}

function walk(directory) {
  return readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
    const path = join(directory, entry.name);
    return entry.isDirectory() ? walk(path) : [path];
  });
}

function contentType(path) {
  return ({
    ".css": "text/css; charset=utf-8",
    ".html": "text/html; charset=utf-8",
    ".ico": "image/x-icon",
    ".js": "text/javascript; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".png": "image/png",
    ".svg": "image/svg+xml",
  })[extname(path)] ?? "application/octet-stream";
}

function platformName(value) {
  if (value === "linux" || value === "darwin" || value === "win32") return value;
  throw new Error(`unsupported binary platform: ${value}`);
}

function architectureName(value) {
  if (value === "x64" || value === "arm64") return value;
  throw new Error(`unsupported binary architecture: ${value}`);
}
