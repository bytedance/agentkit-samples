import { createHash, randomBytes, randomUUID } from "node:crypto";
import { chmodSync, mkdirSync, readFileSync, renameSync, unlinkSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { loadSitulaConfiguration, situlaConfigPaths, writeSitulaConfiguration } from "./config.ts";

const ENDPOINT = "https://signin.volcengine.com";
const AUTHORIZE_PATH = "/authorize/oauth/authorize";
const TOKEN_PATH = "/authorize/oauth/token";
const SCOPE = "Console:All:All";
const CROSS_DEVICE_CLIENT_ID = "trn:signin:::devtools/cross-device";
const AUTH_TTL_MS = 10 * 60_000;
const EXPIRY_SKEW_MS = 60_000;

export interface StsCredentials {
  accessKey: string;
  secretKey: string;
  sessionToken: string;
}

export interface LoginStart {
  id: string;
  authorizationUrl: string;
}

interface PendingLogin {
  state: string;
  verifier: string;
  redirectUri: string;
  clientId: string;
  region: string;
  expiresAt: number;
}

interface TokenResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
  refresh_token?: string;
  id_token?: string;
}

interface LoginCache {
  loginSession: string;
  accessToken: string;
  refreshToken?: string;
  idToken?: string;
  clientId: string;
  endpoint: string;
  issuedAt: string;
  expiresIn: number;
  tokenType: string;
}

/** Local Console OAuth login with PKCE. Browser callers only ever receive the authorize URL. */
export class ConsoleLoginManager {
  #pending = new Map<string, PendingLogin>();

  start(region?: string): LoginStart {
    const id = randomUUID();
    const state = randomBytes(32).toString("base64url");
    const verifier = randomBytes(48).toString("base64url");
    const clientId = CROSS_DEVICE_CLIENT_ID;
    const redirectUri = `${ENDPOINT}${AUTHORIZE_PATH}`;
    this.#pending.set(id, {
      state,
      verifier,
      redirectUri,
      clientId,
      region: region?.trim() || loadSitulaConfiguration().values.VOLCENGINE_REGION,
      expiresAt: Date.now() + AUTH_TTL_MS,
    });
    const query = new URLSearchParams({
      response_type: "code",
      client_id: clientId,
      redirect_uri: redirectUri,
      scope: SCOPE,
      state,
      code_challenge: sha256Base64Url(verifier),
      code_challenge_method: "S256",
    });
    return { id, authorizationUrl: `${ENDPOINT}${AUTHORIZE_PATH}?${query}` };
  }

  async completeRemote(id: string, encodedResponse: string): Promise<void> {
    const pending = this.#take(id);
    let decoded: string;
    try {
      decoded = Buffer.from(encodedResponse.trim(), "base64url").toString("utf8");
    } catch {
      throw new TypeError("authorization response must be base64url encoded");
    }
    const response = new URLSearchParams(decoded);
    await this.#complete(pending, response.get("code"), response.get("state"), response.get("error"));
  }

  async credentials(): Promise<StsCredentials | undefined> {
    const cache = readCache();
    if (!cache) return undefined;
    const expiration = Date.parse(cache.issuedAt) + cache.expiresIn * 1000;
    if (Date.now() >= expiration - EXPIRY_SKEW_MS) {
      if (!cache.refreshToken) return undefined;
      const token = await exchange({
        grant_type: "refresh_token",
        client_id: cache.clientId,
        scope: SCOPE,
        refresh_token: cache.refreshToken,
      }, cache.endpoint);
      const refreshed = credentialsFromAccessToken(token.access_token);
      cache.accessToken = token.access_token;
      cache.refreshToken = token.refresh_token || cache.refreshToken;
      cache.idToken = token.id_token || cache.idToken;
      cache.issuedAt = new Date().toISOString();
      cache.expiresIn = token.expires_in;
      cache.tokenType = token.token_type;
      writeCache(cache);
      return refreshed;
    }
    return credentialsFromAccessToken(cache.accessToken);
  }

  logout(): boolean {
    if (!readCache()) return false;
    try { unlinkSync(cachePath()); } catch (error) {
      if (!(error instanceof Error && "code" in error && error.code === "ENOENT")) throw error;
    }
    return true;
  }

  get active(): boolean {
    return readCache() !== undefined;
  }

  recentToolsScope(region: string, service: string, host: string): string | undefined {
    const loginSession = readCache()?.loginSession;
    if (!loginSession) return undefined;
    return createHash("sha256")
      .update(["situla-recent-tools-v2", loginSession, region, service, host].join("\0"))
      .digest("base64url");
  }

  #take(id: string): PendingLogin {
    const pending = this.#pending.get(id);
    this.#pending.delete(id);
    if (!pending || pending.expiresAt < Date.now()) throw new TypeError("login request is missing or expired");
    return pending;
  }

  async #complete(pending: PendingLogin, code: string | null, state: string | null, error: string | null): Promise<void> {
    if (error) throw new Error(`authorization failed: ${error}`);
    if (!code) throw new TypeError("authorization response did not include a code");
    if (state !== pending.state) throw new Error("authorization state mismatch");
    const token = await exchange({
      grant_type: "authorization_code", code, redirect_uri: pending.redirectUri,
      client_id: pending.clientId, scope: SCOPE, code_verifier: pending.verifier,
    });
    credentialsFromAccessToken(token.access_token);
    const loginSession = sessionFromIdToken(token.id_token);
    writeCache({ loginSession, accessToken: token.access_token, refreshToken: token.refresh_token,
      idToken: token.id_token, clientId: pending.clientId, endpoint: ENDPOINT,
      issuedAt: new Date().toISOString(), expiresIn: token.expires_in, tokenType: token.token_type });
    // Region is a runtime setting; preserve the user's config unless they chose
    // a different region explicitly when starting this login.
    const loaded = loadSitulaConfiguration();
    if (loaded.values.VOLCENGINE_REGION !== pending.region) {
      writeSitulaConfiguration({ ...loaded.values, VOLCENGINE_REGION: pending.region }, loaded.paths);
    }
  }
}

async function exchange(values: Record<string, string>, endpoint = ENDPOINT): Promise<TokenResponse> {
  const response = await fetch(`${endpoint.replace(/\/+$/, "")}${TOKEN_PATH}`, {
    method: "POST", headers: { "content-type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams(values), signal: AbortSignal.timeout(30_000),
  });
  const body = await response.json().catch(() => undefined) as TokenResponse | { error?: string; error_description?: string } | undefined;
  if (!response.ok) throw new Error(`Console login token exchange failed: ${body && "error" in body ? body.error_description || body.error : response.status}`);
  if (!body || !("access_token" in body) || !body.access_token || !body.expires_in) throw new Error("Console login returned an invalid token response");
  return body;
}

function credentialsFromAccessToken(value: string): StsCredentials {
  let parsed: Record<string, unknown>;
  try { parsed = JSON.parse(value) as Record<string, unknown>; } catch { throw new TypeError("Console login access token does not contain STS credentials"); }
  const accessKey = typeof parsed.access_key_id === "string" ? parsed.access_key_id : "";
  const secretKey = typeof parsed.secret_access_key === "string" ? parsed.secret_access_key : "";
  const sessionToken = typeof parsed.session_token === "string" ? parsed.session_token : "";
  if (!accessKey || !secretKey || !sessionToken) throw new TypeError("Console login STS credentials are incomplete");
  return { accessKey, secretKey, sessionToken };
}

function sessionFromIdToken(idToken: string | undefined): string {
  if (!idToken) throw new TypeError("Console login did not return an id token");
  const payload = idToken.split(".")[1];
  if (!payload) throw new TypeError("Console login id token is invalid");
  let parsed: Record<string, unknown>;
  try { parsed = JSON.parse(Buffer.from(payload, "base64url").toString("utf8")) as Record<string, unknown>; } catch { throw new TypeError("Console login id token is invalid"); }
  if (typeof parsed.trn !== "string" || !parsed.trn) throw new TypeError("Console login id token has no trn claim");
  return parsed.trn;
}

function cachePath(): string {
  return join(situlaConfigPaths().directory, "login", "cache", "console-login.json");
}
function readCache(): LoginCache | undefined {
  try { return JSON.parse(readFileSync(cachePath(), "utf8")) as LoginCache; } catch { return undefined; }
}
function writeCache(cache: LoginCache): void {
  const path = cachePath(); const directory = join(situlaConfigPaths().directory, "login", "cache");
  mkdirSync(directory, { recursive: true, mode: 0o700 }); chmodSync(directory, 0o700);
  const temporary = `${path}.${process.pid}.${randomBytes(6).toString("hex")}.tmp`;
  writeFileSync(temporary, `${JSON.stringify(cache)}\n`, { mode: 0o600 }); renameSync(temporary, path);
}
function sha256Base64Url(value: string): string { return createHash("sha256").update(value).digest("base64url"); }
