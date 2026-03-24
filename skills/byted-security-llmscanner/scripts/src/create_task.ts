import * as https from 'https';
import axios from 'axios';
import { loadConfig, getToken } from './common';

async function createEvalTask(
  token: string,
  suiteId: string,
  assetId: string,
  assetType: string,
  config: any
): Promise<string> {
  try {
    const taskName = `eval-task-${new Date().toISOString().replace(/[-:.]/g, '').slice(0, 14)}`;

    const response = await axios.post(
      `${config.host}${config.api_prefix}/CreateEvalTask`,
      {
        TaskName: taskName,
        AssetType: assetType,
        AssetID: assetId,
        EvalSuiteIDs: [suiteId],
        Concurrency: 3,
        TaskType: 'system',
      },
      {
        proxy: false,
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'application/json; charset=UTF-8',
        },
        timeout: 10000,
        httpsAgent: new https.Agent({ rejectUnauthorized: false }),
      }
    );

    const taskId = response.data.Result?.Data;
    if (!taskId) {
      const errMsg = response.data.ResponseMetadata?.Error?.Message || '未知错误';
      if (errMsg.includes('模型连接失败') || errMsg.includes('智能体连接失败') ||
          errMsg.includes('智能体未连接') || errMsg.includes('NeedToEnsureAgentConnect')) {
        console.error('❌ 连接失败！');
        console.error('');
        console.error('💡 提示：资产信息可能配置错误（BaseUrl、ApiKey等）');
        console.error('   请重新提供正确的资产信息，我来为您更新资产');
        process.exit(1);
      }
      console.error(`ERROR: 创建测评任务失败，接口返回：${JSON.stringify(response.data)}`);
      process.exit(1);
    }

    return taskId;
  } catch (error: any) {
    const errMsg = error.response?.data?.ResponseMetadata?.Error?.Message || '';
    if (errMsg.includes('模型连接失败') || errMsg.includes('智能体连接失败') ||
        errMsg.includes('智能体未连接') || errMsg.includes('NeedToEnsureAgentConnect')) {
      console.error('❌ 连接失败！');
      console.error('');
      console.error('💡 提示：资产信息可能配置错误（BaseUrl、ApiKey等）');
      console.error('   请重新提供正确的资产信息，我来为您更新资产');
      process.exit(1);
    }

    console.error(`ERROR: 创建测评任务异常：${error.message}`);
    process.exit(1);
  }
}

async function main() {
  const args = process.argv.slice(2);
  if (args.length !== 3 && args.length !== 4) {
    console.log('参数错误：用法 npx ts-node src/create_task.ts <测评集ID> <资产ID> [AssetType]');
    console.log('\n参数说明：');
    console.log('  测评集ID : 测评集的唯一标识符');
    console.log('  资产ID   : 测评对象的唯一标识符（模型、智能体或OpenClaw）');
    console.log('  AssetType: 资产类型（可选，默认为 model）');
    console.log('    - model    : 大模型');
    console.log('    - agent    : 智能体');
    console.log('    - openclaw : OpenClaw资产');
    process.exit(1);
  }

  const [suiteId, assetId, assetType = 'model'] = args;

  if (assetType !== 'model' && assetType !== 'agent' && assetType !== 'openclaw') {
    console.error('ERROR: AssetType 必须是 model、agent 或 openclaw');
    process.exit(1);
  }

  const config = loadConfig();
  const token = await getToken(config);
  const taskId = await createEvalTask(token, suiteId, assetId, assetType, config);

  const assetTypeName = assetType === 'model' ? '大模型' : (assetType === 'agent' ? '智能体' : 'OpenClaw资产');
  console.log(`测评任务创建成功（${assetTypeName}），任务ID：${taskId}`);
}

main().catch(error => {
  console.error(`ERROR: ${error}`);
  process.exit(1);
});
