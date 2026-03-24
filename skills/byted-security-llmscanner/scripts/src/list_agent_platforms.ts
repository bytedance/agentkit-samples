import * as https from 'https';
import axios from 'axios';
import { loadConfig, getToken } from './common';

async function listAgentPlatforms(token: string, config: any): Promise<any> {
  try {
    const allData: any[] = [];
    let pageNumber = 1;
    const pageSize = 100;
    let totalCount = 0;

    while (true) {
      const response = await axios.post(
        `${config.host}${config.api_prefix}/ListAgentPlatform`,
        {
          PageNumber: pageNumber,
          PageSize: pageSize,
          Filter: {},
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
    console.error(`ERROR: 获取智能体平台列表异常：${error}`);
    process.exit(1);
  }
}

async function getAgentPlatformRequiredVariables(token: string, config: any, platformId: string): Promise<any> {
  try {
    const response = await axios.post(
      `${config.host}${config.api_prefix}/GetAgentChatVars`,
      { PlatformID: platformId },
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

    // 数据结构：response.data.Result.Data.ChatVars 是数组
    return response.data.Result?.Data?.ChatVars || [];
  } catch (error) {
    console.error(`ERROR: 获取平台变量定义异常：${error}`);
    process.exit(1);
  }
}

async function main() {
  const args = process.argv.slice(2);
  const action = args[0];

  const config = loadConfig();
  const token = await getToken(config);

  if (action === 'list') {
    // 查询所有支持的平台
    const platforms = await listAgentPlatforms(token, config);

    // 只显示手动创建的平台（GenerateType 为 manual）
    const manualPlatforms = platforms.filter((p: any) => p.GenerateType === 'manual');

    console.log(JSON.stringify({
      platforms: manualPlatforms.map((p: any) => ({
        id: p.ID,
        name: p.Name,
        platformType: p.PlatformType,
        generateType: p.GenerateType,
        description: p.Description,
      })),
    }, null, 2));
  } else if (action === 'vars') {
    // 查询平台需要的变量
    if (args.length < 2) {
      console.error('ERROR: 请指定平台ID');
      console.error('用法：npx ts-node src/list_agent_platforms.ts vars <PlatformID>');
      console.error('');
      console.error('先运行：npx ts-node src/list_agent_platforms.ts list');
      console.error('查看所有支持的平台ID');
      process.exit(1);
    }

    const platformId = args[1];
    const variables = await getAgentPlatformRequiredVariables(token, config, platformId);

    console.log(JSON.stringify({
      platformId,
      variables: variables.map((v: any) => ({
        name: v.Name,
        field: v.Field,
        type: v.Type,
        description: v.Description,
        placeholder: v.Placeholder,
        required: v.Required,
        default: v.Default,
    })),
    }, null, 2));
  } else {
    console.error('ERROR: 请指定操作类型');
    console.error('用法：');
    console.error('  npx ts-node src/list_agent_platforms.ts list              # 查询所有支持的平台');
    console.error('  npx ts-node src/list_agent_platforms.ts vars <PlatformID>   # 查询平台需要的变量');
    process.exit(1);
  }
}

main().catch(error => {
  console.error(`ERROR: ${error}`);
  process.exit(1);
});
