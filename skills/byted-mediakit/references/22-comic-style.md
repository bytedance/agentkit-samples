# AI 漫剧转绘（Comic Style Transfer）

将短剧/视频转绘为漫画风格或 3D 卡通风格的视频，保留原始音频和剧情。

---

## 限制

| 项目 | 限制 |
|------|------|
| 视频时长 | ≤ 5 分钟 |
| 音频轨道 | 必须包含音频轨道 |
| 并发数 | 同一账号同一时间仅支持 1 个任务 |
| 处理耗时 | 约 10 分钟 / 1 分钟视频 |
| 内容安全 | 视频需通过内容安全审核 |

---

## 参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `Vid` | String | **是** | 视频 ID（上传后获得） |
| `Resolution` | String | **是** | 输出分辨率：`480p` / `720p` / `1080p` |
| `Style` | String | 否 | 转绘风格，默认 `漫画风`。可选：`漫画风` / `3D卡通风格` |

---

## 完整工作流

### Step 1 — 获取视频 ID（Vid）

按 SKILL.md「公共前置步骤：媒资上传」完成上传后获取 Vid。如果用户已有 Vid 则跳过。

### Step 2 — 提交转绘任务

将参数写入 JSON 文件后执行：

```bash
cat > workspace/comic_params.json << 'EOF'
{
  "Vid": "<vid>",
  "Resolution": "720p",
  "Style": "漫画风"
}
EOF

python <SKILL_DIR>/scripts/comic_style.py @workspace/comic_params.json
```

**成功输出示例**：

```json
{
  "Status": "success",
  "OutputJson": {
    "vid": "v0d012xxxx",
    "url": "https://xxx.volcvod.com/xxx.mp4",
    "resolution": "720p",
    "duration": 120.5,
    "filename": "output.mp4"
  }
}
```

将 `url` 返回给用户即可播放/下载转绘后的视频。

### Step 3 — 恢复轮询（仅超时时使用）

如果 Step 2 因轮询超时返回 `resume_hint`，使用以下命令恢复：

```bash
python <SKILL_DIR>/scripts/comic_style.py --poll <VCreativeId> [space_name]
```

也可使用通用轮询脚本：

```bash
python <SKILL_DIR>/scripts/poll_vcreative.py <VCreativeId> [space_name]
```

---

## 错误处理

| 错误信息 | 原因 | 处理方式 |
|---------|------|---------|
| 缺少必填参数 Vid | 未提供视频 ID | 让用户提供 Vid 或先上传视频 |
| 缺少必填参数 Resolution | 未提供输出分辨率 | 让用户选择 480p / 720p / 1080p |
| Style 不合法 | 风格名称不在可选值内 | 提示可选：漫画风 / 3D卡通风格 |
| 视频时长超过限制 | 视频超过 5 分钟 | 建议用户裁剪视频后重试 |
| 提交任务失败 | API 返回错误 | 检查账号权限和并发限制 |
| 轮询超时 | 处理时间较长 | 使用 `--poll` 恢复轮询 |

---

## 计费

参考 [billing-instructions.md](billing-instructions.md)。
