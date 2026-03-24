import * as https from 'https';
import axios from 'axios';
import { loadConfig, getToken } from './common';

async function listRtScenarios(token: string, config: any, assetType?: string): Promise<any> {
  try {
    const allData: any[] = [];
    let pageNumber = 1;
    const pageSize = 100;
    let totalCount = 0;

    while (true) {
      const response = await axios.post(
        `${config.host}${config.api_prefix}/ListRedTeamingScenario`,
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

    // 如果指定了资产类型，过滤适用的剧本
    if (assetType) {
      const filteredData = allData.filter((item: any) => {
        const assetTypes = item.AssetTypes || [];
        return assetTypes.includes(assetType);
      });
      return filteredData;
    }

    return allData;
  } catch (error) {
    console.error(`ERROR: 获取安全测评剧本异常：${error}`);
    process.exit(1);
  }
}

async function main() {
  const args = process.argv.slice(2);
  const assetType = args[0];

  if (assetType && assetType !== 'model' && assetType !== 'agent' && assetType !== 'openclaw') {
    console.error('ERROR: 资产类型必须是 model、agent 或 openclaw');
    process.exit(1);
  }

  const config = loadConfig();
  const token = await getToken(config);
  const scenarios = await listRtScenarios(token, config, assetType);

  if (scenarios.length === 0) {
    console.log('未找到安全测评剧本');
    return;
  }

  console.log(JSON.stringify({
    scenarios: scenarios.map((s: any) => ({
      id: s.ID,
      name: s.Name,
      description: s.Description,
      assetTypes: s.AssetTypes || [],
      status: s.Status,
    })),
  }, null, 2));
}

main().catch(error => {
  console.error(`ERROR: ${error}`);
  process.exit(1);
});
