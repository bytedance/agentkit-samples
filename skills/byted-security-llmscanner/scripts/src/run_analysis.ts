import * as https from 'https';
import axios from 'axios';
import * as fs from 'fs';
import * as path from 'path';
import { exec } from 'child_process';
import { promisify } from 'util';
import { loadConfig, getToken, getTaskDataFile } from './common';

const execAsync = promisify(exec);

const STATUS_MAP: Record<number, string> = {
  0: '待测评',
  1: '测评中',
  2: '测评成功',
  3: '测评异常',
  5: '暂停测评',
  6: '终止测评',
};

const TERMINAL_STATUS = [2, 3, 5, 6];

function checkLocalData(taskId: string): boolean {
  const dataFile = getTaskDataFile(taskId);
  return fs.existsSync(dataFile);
}

async function analyzeLocalData(taskId: string): Promise<boolean> {
  console.log('📂 检测到本地已有任务数据，开始分析...');

  try {
    const { stdout } = await execAsync(`npx ts-node src/analyze_task_data.ts ${taskId}`);
    console.log(stdout);
    return true;
  } catch (error: any) {
    console.error(`❌ 分析失败：${error.stderr || error.message}`);
    return false;
  }
}

async function getTaskStatus(token: string, taskId: string, config: any): Promise<any> {
  try {
    const response = await axios.post(
      `${config.host}${config.api_prefix}/GetEvalTaskDetail`,
      { TaskID: taskId },
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
      console.error(`❌ 获取任务状态失败：${errMsg}`);
      process.exit(1);
    }

    return response.data.Result?.Data;
  } catch (error) {
    console.error(`❌ 获取任务状态异常：${error}`);
    process.exit(1);
  }
}

async function getTaskData(token: string, taskId: string, config: any): Promise<any> {
  const allResults: any[] = [];
  let pageNumber = 1;
  const pageSize = 100;

  while (true) {
    try {
      const response = await axios.post(
        `${config.host}${config.api_prefix}/ListEvalResultByData`,
        {
          PageNumber: pageNumber,
          PageSize: pageSize,
          TaskID: taskId,
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

      if (response.data.ResponseMetadata?.Error) {
        const errMsg = response.data.ResponseMetadata.Error.Message || '未知错误';
        console.error(`❌ 获取任务数据失败：${errMsg}`);
        process.exit(1);
      }

      const result = response.data.Result || {};
      const pageData = result.Data || [];
      const totalCount = result.TotalCount || 0;

      if (!pageData || pageData.length === 0) {
        break;
      }

      allResults.push(...pageData);

      if (allResults.length >= totalCount) {
        break;
      }

      pageNumber++;
    } catch (error) {
      console.error(`❌ 获取任务数据异常：${error}`);
      process.exit(1);
    }
  }

  return {
    TaskID: taskId,
    TotalCount: allResults.length,
    Data: allResults,
  };
}

function saveTaskData(taskId: string, data: any): string {
  const dataFile = getTaskDataFile(taskId);
  const dataDir = path.dirname(dataFile);

  if (!fs.existsSync(dataDir)) {
    fs.mkdirSync(dataDir, { recursive: true });
  }

  fs.writeFileSync(dataFile, JSON.stringify(data, null, 2));
  return dataFile;
}

async function fetchAndAnalyze(taskId: string, config: any): Promise<boolean> {
  console.log('📥 正在拉取任务数据...');
  const token = await getToken(config);
  const taskData = await getTaskData(token, taskId, config);
  const dataFile = saveTaskData(taskId, taskData);

  console.log(`💾 数据已保存到：${dataFile}`);
  console.log(`📊 数据总量：${taskData.TotalCount || 0} 条`);
  console.log();

  console.log('🔍 正在分析数据...');
  return await analyzeLocalData(taskId);
}

function estimateRemainingTime(execCount: number, total: number, avgTimePerItem = 2): number | null {
  if (execCount === 0 || total === 0) {
    return null;
  }

  const remaining = total - execCount;
  return remaining * avgTimePerItem;
}

function formatTime(seconds: number | null): string {
  if (seconds === null) {
    return '未知';
  }

  if (seconds < 60) {
    return `${Math.floor(seconds)}秒`;
  } else if (seconds < 3600) {
    return `${Math.floor(seconds / 60)}分钟`;
  } else {
    return `${Math.floor(seconds / 3600)}小时`;
  }
}

async function main() {
  const args = process.argv.slice(2);
  if (args.length !== 1) {
    console.log('用法：npx ts-node src/run_analysis.ts <TaskID>');
    console.log('\n功能：');
    console.log('  - 查询任务状态');
    console.log('  - 如果任务成功完成，自动拉取数据并分析');
    console.log('  - 如果任务未完成，显示执行进度和预估时间');
    console.log('  - 如果任务异常/暂停/终止，显示状态并提示无法分析');
    process.exit(1);
  }

  const taskId = args[0];
  const config = loadConfig();

  console.log(`🔍 分析测评任务：${taskId}`);
  console.log(`⏰ 时间：${new Date().toLocaleString('zh-CN')}`);
  console.log('='.repeat(60));

  if (checkLocalData(taskId)) {
    await analyzeLocalData(taskId);
  } else {
    console.log('📊 正在查询任务状态...');

    const token = await getToken(config);
    const taskDetail = await getTaskStatus(token, taskId, config);
    const taskStatus = taskDetail.TaskStatus;
    const statusName = STATUS_MAP[taskStatus] || '未知状态';

    console.log(`✅ 任务状态：${statusName}`);

    if (TERMINAL_STATUS.includes(taskStatus)) {
      if (taskStatus === 2) {
        console.log();
        await fetchAndAnalyze(taskId, config);
      } else {
        console.log(`⚠️  任务未正常完成，状态：${statusName}`);
        console.log('   无法进行数据分析');
      }
    } else {
      console.log();
      console.log('⏳ 任务仍在执行中...');

      const execCount = taskDetail.ExecCount || 0;
      const total = taskDetail.Total || 0;

      if (total > 0) {
        const progress = (execCount / total) * 100;
        console.log(`   执行进度：${execCount}/${total} (${progress.toFixed(1)}%)`);

        const remainingSeconds = estimateRemainingTime(execCount, total);
        const remainingTime = formatTime(remainingSeconds);
        console.log(`   预计剩余时间：${remainingTime}`);
      } else {
        console.log('   执行进度：暂无数据');
      }

      console.log();
      console.log('💡 提示：');
      console.log('   - 任务正在后台执行');
      console.log('   - 请稍后再次运行此命令查看分析结果');
    }
  }
}

main().catch(error => {
  console.error(`ERROR: ${error}`);
  process.exit(1);
});
