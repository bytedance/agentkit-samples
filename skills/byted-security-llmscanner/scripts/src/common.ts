import axios from 'axios';
import * as fs from 'fs';
import * as path from 'path';
import * as https from 'https';

const SCRIPT_DIR = path.join(__dirname, '..');
const DATA_DIR = path.join(SCRIPT_DIR, 'data');

if (!fs.existsSync(DATA_DIR)) {
  fs.mkdirSync(DATA_DIR, { recursive: true });
}

const CONFIG_FILE = path.join(SCRIPT_DIR, 'config.ts');
const TOKEN_CACHE_FILE = path.join(DATA_DIR, 'token_cache.json');
const SUITE_CACHE_FILE = path.join(DATA_DIR, 'suite_cache.json');
const ASSET_CACHE_FILE = path.join(DATA_DIR, 'asset_cache.json');
const AGENT_CACHE_FILE = path.join(DATA_DIR, 'agent_cache.json');
const OPENCLAW_CACHE_FILE = path.join(DATA_DIR, 'openclaw_cache.json');
const SCENARIO_CACHE_FILE = path.join(DATA_DIR, 'scenario_cache.json');

export interface Config {
  username: string;
  password: string;
  host: string;
  api_prefix: string;
  cache_ttl: number;
  cache_ttl_token: number;
  cache_ttl_suite: number;
  cache_ttl_asset: number;
  cache_ttl_agent: number;
  cache_ttl_openclaw: number;
  cache_ttl_scenario: number;
  data_dir: string;
}

export interface CacheData<T> {
  cache_time: number;
  data: T;
}

export interface TokenCache {
  Token: string;
  Expire: number;
}

export function loadConfig(): Config {
  try {
    const configContent = fs.readFileSync(CONFIG_FILE, 'utf-8');
    const config: Partial<Config> = {};

    const lines = configContent.split('\n');
    for (const line of lines) {
      const trimmed = line.trim();
      if (trimmed.startsWith('#') || !trimmed.includes('=')) continue;

      const [key, ...valueParts] = trimmed.split('=');
      const value = valueParts.join('=').trim().replace(/^["']|["']$/g, '');
      const keyName = key.trim();

      // 字段映射：兼容不同格式的配置文件
      if (keyName === 'login_host' || keyName === 'api_host') {
        config['host' as keyof Config] = value as any;
        continue;
      }

      // 数字类型的配置项
      if (keyName.startsWith('cache_ttl') || keyName === 'cache_ttl') {
        config[keyName as keyof Config] = parseInt(value, 10) as any;
      } else {
        config[keyName as keyof Config] = value as any;
      }
    }

    return config as Config;
  } catch (error) {
    console.error(`ERROR: 加载配置失败：${error}`);
    process.exit(1);
  }
}

export async function getToken(config: Config): Promise<string> {
  if (fs.existsSync(TOKEN_CACHE_FILE)) {
    try {
      const cacheContent = fs.readFileSync(TOKEN_CACHE_FILE, 'utf-8');
      const cache: TokenCache = JSON.parse(cacheContent);

      if (cache.Token && cache.Expire && Date.now() / 1000 < cache.Expire - 600) {
        return cache.Token;
      }
    } catch {
      // Ignore cache errors
    }
  }

  try {
    const response = await axios.post(
      `${config.host}${config.api_prefix}/Login`,
      {
        UserName: config.username,
        Password: config.password,
      },
      {
        headers: { 'Content-Type': 'application/json' },
        timeout: 10000,
        proxy: false,
        httpsAgent: new https.Agent({ rejectUnauthorized: false }),
      }
    );

    if (response.data.ResponseMetadata?.Error) {
      const errMsg = response.data.ResponseMetadata.Error.Message || '未知错误';
      console.error(`ERROR: 登录失败：${errMsg}`);
      process.exit(1);
    }

    const resultData = response.data.Result?.Data || {};
    const token = resultData.Token;
    const expire = resultData.Expire;

    if (!token) {
      console.error('ERROR: 获取Token失败');
      process.exit(1);
    }

    try {
      fs.writeFileSync(TOKEN_CACHE_FILE, JSON.stringify({ Token: token, Expire: expire }, null, 2));
    } catch {
      // Ignore write errors
    }

    return token;
  } catch (error) {
    console.error(`ERROR: 获取Token异常：${error}`);
    process.exit(1);
  }
}

export function getCachedData<T>(cacheFile: string, ttl: number): T | null {
  if (ttl <= 0) return null;
  if (!fs.existsSync(cacheFile)) return null;

  try {
    const cacheContent = fs.readFileSync(cacheFile, 'utf-8');
    const cache: CacheData<T> = JSON.parse(cacheContent);

    if (Date.now() / 1000 - cache.cache_time < ttl) {
      return cache.data;
    }
  } catch {
    // Ignore cache errors
  }

  return null;
}

export function saveCachedData<T>(cacheFile: string, data: T): void {
  try {
    const cacheContent: CacheData<T> = {
      cache_time: Date.now() / 1000,
      data,
    };
    fs.writeFileSync(cacheFile, JSON.stringify(cacheContent, null, 2));
  } catch {
    // Ignore write errors
  }
}

export function clearCache(cacheFile: string): void {
  if (fs.existsSync(cacheFile)) {
    try {
      fs.unlinkSync(cacheFile);
    } catch {
      // Ignore delete errors
    }
  }
}

export function getTaskDataFile(taskId: string): string {
  return path.join(DATA_DIR, `${taskId}.json`);
}

export function getReportFile(taskId: string): string {
  return path.join(DATA_DIR, `${taskId}_report.txt`);
}

export { TOKEN_CACHE_FILE, SUITE_CACHE_FILE, ASSET_CACHE_FILE, AGENT_CACHE_FILE, OPENCLAW_CACHE_FILE, SCENARIO_CACHE_FILE, DATA_DIR };
