import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {bundle} from '@remotion/bundler';
import {renderMedia, selectComposition} from '@remotion/renderer';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const entryPoint = path.join(__dirname, 'src', 'index.tsx');

// Config path: --config=/path/to/config.json  or  first positional arg
const args = process.argv.slice(2);
const configFlag = args.find((arg) => arg.startsWith('--config='));
const configArgIndex = args.findIndex((arg) => arg === '--config');
const defaultConfigPath = path.join(__dirname, '..', 'temp', 'effects_config.json');
const configPath =
  (configFlag ? configFlag.split('=')[1] : null) ??
  (configArgIndex >= 0 ? args[configArgIndex + 1] : null) ??
  args[0] ??
  defaultConfigPath;

// Output dir: --out-dir=/path/to/dir  (default: ../temp/effects relative to this script)
const outDirFlag = args.find((arg) => arg.startsWith('--out-dir='));
const outDirArgIndex = args.findIndex((arg) => arg === '--out-dir');
const defaultOutDir = path.join(__dirname, '..', 'temp', 'effects');
const outputBaseDir =
  (outDirFlag ? outDirFlag.split('=')[1] : null) ??
  (outDirArgIndex >= 0 ? args[outDirArgIndex + 1] : null) ??
  defaultOutDir;

const config = JSON.parse(fs.readFileSync(configPath, 'utf-8'));
const chapterTitles = Array.isArray(config.chapterTitles) ? config.chapterTitles : [];
const keyPhrases = Array.isArray(config.keyPhrases) ? config.keyPhrases : [];
const lowerThirds = Array.isArray(config.lowerThirds) ? config.lowerThirds : [];
const quotes = Array.isArray(config.quotes) ? config.quotes : [];
const danmakuBursts = Array.isArray(config.danmakuBursts) ? config.danmakuBursts : [];

const bundleOutDir = path.join(__dirname, '.remotion-bundle');
const useServeUrl = Boolean(process.env.REMOTION_SERVE_URL);
const serveUrl =
  process.env.REMOTION_SERVE_URL ??
  (await bundle({
    entryPoint,
    outDir: bundleOutDir,
    webpackOverride: (config) => config,
  }));

console.log(`serveUrl: ${serveUrl}`);

const chromiumOptions = {
  gl: 'angle',
  headless: true,
};

const compositionCache = {};
const getComposition = async (id) => {
  if (!compositionCache[id]) {
    compositionCache[id] = await selectComposition({
      serveUrl,
      id,
      inputProps: {config},
      chromiumOptions,
    });
  }
  return compositionCache[id];
};

const renderEffect = async (id, inputProps, outputLocation) => {
  const baseComposition = await getComposition(id);
  const composition = {
    ...baseComposition,
    props: inputProps,
  };
  fs.mkdirSync(path.dirname(outputLocation), {recursive: true});
  await renderMedia({
    composition,
    serveUrl,
    codec: 'prores',
    proResProfile: '4444',
    pixelFormat: 'yuva444p10le',
    imageFormat: 'png',
    preferLossless: true,
    outputLocation,
    inputProps: {config, ...inputProps},
    timeoutInMilliseconds: 120000,
    logLevel: 'error',
    chromiumOptions,
    concurrency: 1,
    onBrowserLog: (log) => {
      if (log.type === 'error') console.log(`[browser] ${log.type}: ${log.text}`);
    },
  });
};

const slugify = (value) =>
  String(value ?? '')
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/(^-|-$)+/g, '');

let exitCode = 0;
try {
  const totalEffects =
    chapterTitles.length +
    keyPhrases.length +
    lowerThirds.length +
    quotes.length +
    danmakuBursts.length;

  if (totalEffects === 0) {
    throw new Error('effects_config 中未找到可渲染的特效数据');
  }

  console.log(`共 ${totalEffects} 个特效待渲染`);

  for (let i = 0; i < chapterTitles.length; i++) {
    const ch = chapterTitles[i];
    const inputProps = {
      number: ch.number,
      title: ch.title,
      subtitle: ch.subtitle,
      theme: ch.theme ?? config.theme ?? 'douyin',
      durationMs: ch.durationMs ?? 3000,
    };
    const outputLocation = path.join(outputBaseDir, `chapterTitles-${i}.mov`);
    await renderEffect('ChapterTitle', inputProps, outputLocation);
    console.log(`✅ chapterTitles-${i} -> ${outputLocation}`);
  }

  for (let i = 0; i < keyPhrases.length; i++) {
    const phrase = keyPhrases[i];
    const durationMs =
      phrase.durationMs ??
      (typeof phrase.endMs === 'number' && typeof phrase.startMs === 'number'
        ? Math.max(phrase.endMs - phrase.startMs, 0)
        : 2000);
    const inputProps = {
      text: phrase.text,
      style: phrase.style ?? 'emphasis',
      theme: phrase.theme ?? config.theme ?? 'douyin',
      position: phrase.position ?? 'top',
      durationMs,
    };
    const outputLocation = path.join(outputBaseDir, `keyPhrases-${i}.mov`);
    await renderEffect('fancy-text', inputProps, outputLocation);
    console.log(`✅ keyPhrases-${i} -> ${outputLocation}`);
  }

  for (let i = 0; i < lowerThirds.length; i++) {
    const lt = lowerThirds[i];
    const inputProps = {
      name: lt.name,
      role: lt.role ?? '',
      company: lt.company ?? '',
      theme: lt.theme ?? config.theme ?? 'douyin',
      durationMs: lt.durationMs ?? 5000,
    };
    const outputLocation = path.join(outputBaseDir, `lowerThirds-${i}.mov`);
    await renderEffect('lower-third', inputProps, outputLocation);
    console.log(`✅ lowerThirds-${i} -> ${outputLocation}`);
  }

  for (let i = 0; i < quotes.length; i++) {
    const quote = quotes[i];
    const inputProps = {
      text: quote.text,
      author: quote.author,
      theme: quote.theme ?? config.theme ?? 'douyin',
      position: quote.position ?? 'bottom',
      durationMs: quote.durationMs ?? 5000,
    };
    const outputLocation = path.join(outputBaseDir, `quotes-${i}.mov`);
    await renderEffect('quote-callout', inputProps, outputLocation);
    console.log(`✅ quotes-${i} -> ${outputLocation}`);
  }

  for (let i = 0; i < danmakuBursts.length; i++) {
    const burst = danmakuBursts[i];
    const inputProps = {
      messages: burst.messages ?? [],
      highlight: burst.highlight,
      theme: burst.theme ?? config.theme ?? 'douyin',
      durationMs: burst.durationMs ?? 3000,
    };
    const outputLocation = path.join(outputBaseDir, `danmakuBursts-${i}.mov`);
    await renderEffect('danmaku-burst', inputProps, outputLocation);
    console.log(`✅ danmakuBursts-${i} -> ${outputLocation}`);
  }

} catch (error) {
  exitCode = 1;
  console.error(error);
} finally {
  if (!useServeUrl) {
    fs.rmSync(bundleOutDir, {recursive: true, force: true});
  }
  process.exit(exitCode);
}
