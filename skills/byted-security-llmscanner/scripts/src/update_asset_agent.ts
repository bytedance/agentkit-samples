import * as https from 'https';
import axios from 'axios';
import { loadConfig, getToken } from './common';

async function updateAgentAsset(
  token: string,
  agentId: string,
  name: string,
  platformType: string,
  chatVars: Record<string, any>,
  config: any,
  maxRetries: number = 3
): Promise<void> {
  let lastError: any = null;

  for (let attempt = 1; attempt <= maxRetries; attempt++) {
    try {
      if (attempt > 1) {
        console.log(`INFO: 第 ${attempt} 次尝试更新智能体资产...`);
      }

      console.log('INFO: 正在调用更新智能体资产接口...');

      const response = await axios.post(
        `${config.host}${config.api_prefix}/UpdateAgent`,
        {
          AssetID: agentId,
          Name: name,
          PlatformID: platformType,
          ChatVars: chatVars,
        },
        {
        proxy: false,
          headers: {
            Authorization: `Bearer ${token}`,
            'Content-Type': 'application/json; charset=UTF-8',
          },
          timeout: 300000, // 5分钟超时
          httpsAgent: new https.Agent({ rejectUnauthorized: false }),
        }
      );

      console.log('INFO: 接口调用成功，正在解析响应...');

      if (response.data.ResponseMetadata?.Error) {
        const errMsg = response.data.ResponseMetadata.Error.Message || '未知错误';
        console.error(`ERROR: 更新智能体资产失败：${errMsg}`);
        process.exit(1);
      }

      console.log('INFO: 智能体资产更新成功');
      return;
    } catch (error: any) {
      lastError = error;

      // 判断是否为超时错误
      const isTimeout = error.code === 'ECONNABORTED' || error.message?.includes('timeout');

      if (isTimeout && attempt < maxRetries) {
        console.warn(`WARN: 请求超时，将在3秒后重试 (${attempt}/${maxRetries})...`);
        await new Promise(resolve => setTimeout(resolve, 3000));
        continue;
      }

      if (attempt < maxRetries) {
        console.warn(`WARN: 请求失败，将在3秒后重试 (${attempt}/${maxRetries})...`);
        console.warn(`WARN: 错误信息：${error.message}`);
        await new Promise(resolve => setTimeout(resolve, 3000));
        continue;
      }
    }
  }

  // 所有重试都失败
  console.error(`ERROR: 更新智能体资产异常（已重试 ${maxRetries} 次）：${lastError}`);
  if (lastError.response) {
    console.error(`ERROR: 响应状态码：${lastError.response.status}`);
    console.error(`ERROR: 响应数据：${JSON.stringify(lastError.response.data)}`);
  }
  process.exit(1);
}

function parseChatVars(args: string[]): Record<string, any> {
  const chatVars: Record<string, any> = {};

  for (let i = 0; i < args.length; i++) {
    const arg = args[i];
    if (arg.startsWith('--') && arg.includes('=')) {
      const [key, ...valueParts] = arg.slice(2).split('=');
      const value = valueParts.join('=');

      // 尝试解析为 JSON，如果不是则作为字符串
      try {
        chatVars[key] = JSON.parse(value);
      } catch {
        chatVars[key] = value;
      }
    }
  }

  return chatVars;
}

async function main() {
  const args = process.argv.slice(2);

  if (args.length < 3) {
    console.log('参数错误：用法 npx ts-node src/update_asset_agent.ts <AgentID> <Name> <PlatformID> [options]');
    console.log('\n参数说明：');
    console.log('  AgentID     : 智能体资产ID');
    console.log('  Name        : 智能体资产名称');
    console.log('  PlatformID  : 平台ID（通过 list_agent_platforms.ts list 查询，使用返回的 id 字段）');
    console.log('\n选项（ChatVars）：');
    console.log('  --key=value : 智能体对话变量，可多个');
    console.log('                支持 JSON 格式，例如：--config={"url":"https://..."}');
    console.log('\n示例：');
    console.log('  # 查询支持的平台');
    console.log('  npx ts-node src/list_agent_platforms.ts list');
    console.log('');
    console.log('  # 查询平台需要的变量（使用平台ID）');
    console.log('  npx ts-node src/list_agent_platforms.ts vars <PlatformID>');
    console.log('');
    console.log('  # 更新智能体资产（使用平台ID）');
    console.log('  npx ts-node src/update_asset_agent.ts agent-id my-agent b0226c4550aa4791a8c19a118a5f8ef5 --api_key=sk-xxx');
    process.exit(1);
  }

  const agentId = args[0];
  const name = args[1];
  const platformId = args[2];
  const chatVars = parseChatVars(args.slice(3));

  console.log('='.repeat(50));
  console.log('智能体测评资产更新工具');
  console.log('='.repeat(50));
  console.log(`\n【Step 1】资产信息`);
  console.log(`  AgentID     ：${agentId}`);
  console.log(`  Name        ：${name}`);
  console.log(`  PlatformID  ：${platformId}`);
  if (Object.keys(chatVars).length > 0) {
    console.log(`  ChatVars     ：${JSON.stringify(chatVars)}`);
  }

  const config = loadConfig();

  console.log('\n【Step 2】获取鉴权Token...');
  const token = await getToken(config);
  console.log('INFO: Token获取成功');

  console.log('\n【Step 3】更新智能体资产...');
  await updateAgentAsset(token, agentId, name, platformId, chatVars, config);

  console.log('\n' + '='.repeat(50));
  console.log(`✅ 智能体资产更新成功！`);
  console.log(`   资产ID：${agentId}`);
  console.log('='.repeat(50));
}

main().catch(error => {
  console.error(`ERROR: ${error}`);
  process.exit(1);
});
