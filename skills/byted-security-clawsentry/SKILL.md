---
description: Install and configure the security-related plugins required by OpenClaw, including the `ai-assistant-security-openclaw` plugins. Use this skill when you want to complete installation and basic configuration of these plugins for an OpenClaw environment in one go.
name: byted-security-clawsentry
---

# ClawSentry

## Agent Rules

IMPORTANT: You MUST follow these steps EXACTLY when using this skill:

1. FIRST: Verify Node.js is installed on the system (version 14 or higher).
2. SECOND: Execute the script `node {baseDir}/scripts/bundle.js`.
3. THIRD: Verify the script executed successfully by checking:
   - Check the script exit code: 0 means success, non-0 means failure
   - Look for success output: "Login URL generated successfully:" in the script output
   - Look for the line that starts with `[LOGIN_URL]:` in the script output
   - Check if `{baseDir}/.state/login_state.json` file exists and contains a valid `loginUrl` field
   - If the file doesn't exist, wait a few seconds and try again
   - If you can't find the files, try looking in `.openclaw/skills/ClawSentry/scripts/` directory

4. FOURTH: After confirming the script succeeded, get the login URL using ONE of these methods (in this priority order):
   - Extract from the script output by looking for the line that starts with `[LOGIN_URL]:`
   - Read from `{baseDir}/.state/login_state.json` file (look for the `loginUrl` field)

5. FIFTH: Send the login URL to the user along with this message: "After completing login, please send me a message saying you have successfully logged in (e.g., '我已经注册成功了', '我已经登录成功了', '我已经注册好了', '登录好了', '登录上了')."
6. SIXTH: After sending the login URL to the user, you MUST perform the following monitoring for 10 minutes (600 seconds):
   a. EVERY MINUTE, check if the process `bundle.js --login-token` is running using the command: `ps aux | grep "bundle.js --login-token"`
   b. If the process IS running: continue monitoring until the 10 minutes expire
   c. If the process IS NOT running:
   i. Read `{baseDir}/.state/login_state.json` file and check the `enable` field
   ii. If `enable` is `true`: END the conversation immediately
   iii. If `enable` is `false`: - Read `loginToken` and `deviceFingerprint` from `{baseDir}/.state/login_state.json` - Restart the process with: `node {baseDir}/scripts/bundle.js --login-token [loginToken] --device-fingerprint [deviceFingerprint]`
   d. Stop monitoring after 10 minutes have elapsed

DO NOT skip any steps. DO NOT modify the order of steps. ALWAYS verify the script succeeded before proceeding.

## Use Cases

- Use this skill when you need to install and prepare the `ai-assistant-security-openclaw` plugins for the OpenClaw environment on the current machine.
- Trigger this skill when the user mentions requirements such as "install clawSentry / ai-assistant-security-openclaw plugin / install byted-security-clawsentry / 使用byted-security-clawsentry技能安装安全插件".

## Steps

### 1. Verify Node.js is installed:

Ensure Node.js (version 14 or higher) is installed on the system. You can check with:

```bash
node --version
```

### 2. Execute the combined script to install plugin and generate login link:

```bash
node {baseDir}/scripts/bundle.js
```

After the script completes:

- The script will display the login URL directly. You can also extract it from the output by looking for the line that starts with `[LOGIN_URL]:`
- You can also read the login URL from `{baseDir}/.state/login_state.json` file (look for the `loginUrl` field). If the file doesn't exist, try reading it again after a few seconds. If you can't find the files, try looking in `.openclaw/skills/ClawSentry/scripts/` directory.
- Send the login URL to the user along with this message: "After completing login, please send me a message saying you have successfully logged in (e.g., '我已经注册成功了', '我已经登录成功了', '我已经注册好了', '登录好了', '登录上了')."
