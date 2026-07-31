import { useState, type ReactNode } from "react";
import { completeRemoteConsoleLogin, startConsoleLogin } from "../api";
import { messageOf } from "../display";

export function ConsoleLogin({ onComplete }: { onComplete: () => void }): ReactNode {
  const [region, setRegion] = useState("cn-beijing");
  const [pending, setPending] = useState<{ id: string; authorizationUrl: string }>();
  const [response, setResponse] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string>();

  const begin = async () => {
    setBusy(true); setError(undefined);
    try {
      setPending(await startConsoleLogin(region));
    } catch (loginError) { setError(messageOf(loginError)); } finally { setBusy(false); }
  };
  const finishRemote = async () => {
    if (!pending || !response.trim()) return;
    setBusy(true); setError(undefined);
    try { await completeRemoteConsoleLogin(pending.id, response); onComplete(); }
    catch (loginError) { setError(messageOf(loginError)); } finally { setBusy(false); }
  };

  return <main className="console-login"><section>
    <p className="eyebrow">Situla · AgentKit</p>
    <h1>登录火山引擎</h1>
    <p>通过控制台 OAuth 登录以获取可自动刷新的临时 STS 凭证。凭证仅保存在本机 bridge。</p>
    <label>地域<input value={region} onChange={(event) => setRegion(event.target.value)} disabled={busy} /></label>
    {!pending ? <button className="primary" onClick={() => void begin()} disabled={busy}>{busy ? "正在准备…" : "生成授权链接"}</button> : <>
      <p className="login-instruction">在任意设备打开以下链接并完成登录，然后粘贴页面显示的授权码：</p>
      <textarea className="login-url-text" readOnly value={pending.authorizationUrl} aria-label="授权链接" />
      <a className="login-url" href={pending.authorizationUrl} target="_blank" rel="noreferrer">打开授权页面</a>
      <textarea value={response} onChange={(event) => setResponse(event.target.value)} placeholder="粘贴 Base64 授权响应" disabled={busy} />
      <button className="primary" onClick={() => void finishRemote()} disabled={busy || !response.trim()}>{busy ? "正在验证…" : "完成登录"}</button>
    </>}
    {error && <p className="login-error">{error}</p>}
  </section></main>;
}
