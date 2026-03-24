import * as https from 'https';
import axios from 'axios';
import { loadConfig, getToken } from './common';

async function createRtTask(
  token: string,
  taskName: string,
  assetId: string,
  assetType: string,
  scenarioId: string,
  config: any
): Promise<void> {
  try {
    const response = await axios.post(
      `${config.host}${config.api_prefix}/CreateRedTeamingTaskBatch`,
      {
        Name: taskName,
        AssetType: assetType,
        AssetIDs: [assetId],
        ScenarioIDs: [scenarioId],
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

    if (response.data.ResponseMetadata?.Error) {
      const errMsg = response.data.ResponseMetadata.Error.Message || '未知错误';
      console.error(`ERROR: 创建安全测评任务失败：${errMsg}`);
      process.exit(1);
    }
  } catch (error: any) {
    console.error(`ERROR: 创建安全测评任务异常：${error.message}`);
    process.exit(1);
  }
}

async function getRtTaskByName(token: string, taskName: string, config: any): Promise<any> {
  try {
    const allData: any[] = [];
    let pageNumber = 1;
    const pageSize = 100;
    let totalCount = 0;

    while (true) {
      const response = await axios.post(
        `${config.host}${config.api_prefix}/ListRedTeamingTaskPage`,
        {
          PageNumber: pageNumber,
          PageSize: pageSize,
          Filter: { Name: taskName },
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

      const result = response.data.Result || {};
      const pageData = result.Data || [];
      totalCount = result.TotalCount || 0;

      if (!pageData || pageData.length === 0) {
        break;
      }

      allData.push(...pageData);

      if (allData.length >= totalCount) {
        break;
      }

      pageNumber++;
    }

    return allData;
  } catch (error) {
    console.error(`ERROR: 查询安全测评任务异常：${error}`);
    process.exit(1);
  }
}

async function main() {
  const args = process.argv.slice(2);

  if (args.length !== 4 && args.length !== 5) {
    console.log('参数错误：用法 npx ts-node src/create_rt_task.ts <TaskName> <AssetID> <AssetType> <ScenarioID>');
    console.log('\n参数说明：');
    console.log('  TaskName   : 任务名称');
    console.log('  AssetID    : 测评对象ID（模型、智能体或OpenClaw）');
    console.log('  AssetType  : 资产类型');
    console.log('    - model    : 大模型');
    console.log('    - agent    : 智能体');
    console.log('    - openclaw : OpenClaw资产');
    console.log('  ScenarioID : 安全测评剧本ID');
    console.log('\n使用流程：');
    console.log('  1. 查询可用测评对象：npx ts-node src/fetch_lists.ts [ModalTypes]');
    console.log('  2. 查询安全测评剧本：npx ts-node src/list_rt_scenarios.ts [AssetType]');
    console.log('  3. 创建安全测评任务：npx ts-node src/create_rt_task.ts <TaskName> <AssetID> <AssetType> <ScenarioID>');
    process.exit(1);
  }

  const [taskName, assetId, assetType, scenarioId] = args;

  if (assetType !== 'model' && assetType !== 'agent' && assetType !== 'openclaw') {
    console.error('ERROR: AssetType 必须是 model、agent 或 openclaw');
    process.exit(1);
  }

  const config = loadConfig();
  const token = await getToken(config);

  // 创建任务
  await createRtTask(token, taskName, assetId, assetType, scenarioId, config);

  // 查询任务信息
  const tasks = await getRtTaskByName(token, taskName, config);

  if (tasks.length === 0) {
    console.error('ERROR: 创建任务成功，但未找到任务信息');
    process.exit(1);
  }

  const task = tasks[0];
  console.log(`安全测评任务创建成功`);
  console.log(`任务ID：${task.ID}`);
  console.log(`任务名称：${task.Name}`);
  console.log(`任务状态：${task.Status}`);
}

main().catch(error => {
  console.error(`ERROR: ${error}`);
  process.exit(1);
});
