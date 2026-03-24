import * as https from 'https';
import axios from 'axios';
import { loadConfig, getToken } from './common';

// 状态映射（根据swagger文档中的Status字段定义）
const STATUS_MAP: Record<string, string> = {
  'nsyncing': '等待处理',
  'success': '执行成功',
  'failed': '执行失败',
  'not_sync': '未同步',
};

// 数字状态映射（兼容API返回数字状态的情况）
const NUMERIC_STATUS_MAP: Record<number, string> = {
  10: '等待处理',
  20: '处理中',
  30: '异常',
  40: '完成',
};

// 终止状态（任务完成或失败）
const TERMINAL_STATUS = [30, 40]; // 30=异常, 40=完成

async function getRtTaskReport(token: string, taskId: string, config: any): Promise<any> {
  try {
    const response = await axios.post(
      `${config.host}${config.api_prefix}/GetRedTeamingTaskReport`,
      { ID: taskId },
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
      console.error(`ERROR: 获取任务报告失败：${errMsg}`);
      process.exit(1);
    }

    // 根据swagger定义，响应数据可能在 Result.Data 中
    // 如果 Result.Data 存在，使用它；否则使用 Result
    const resultData = response.data.Result?.Data !== undefined ? response.data.Result.Data : response.data.Result;
    
    return resultData;
  } catch (error) {
    console.error(`ERROR: 获取任务报告异常：${error}`);
    process.exit(1);
  }
}

function analyzeRtTaskReport(taskId: string, report: any): string {
  const reportLines: string[] = [];

  // 报告头部
  reportLines.push('='.repeat(80));
  reportLines.push('📊 安全测评任务分析报告');
  reportLines.push('='.repeat(80));

  // ========== 1. 基本信息 ==========
  reportLines.push('\n📋 一、基本信息');
  reportLines.push('-'.repeat(80));
  reportLines.push(`资产名称：${report.AssetName || '未知'}`);
  reportLines.push(`资产类型：${report.AssetType || '未知'}`);
  reportLines.push(`开始时间：${report.StartTime ? new Date(report.StartTime * 1000).toLocaleString('zh-CN') : '未知'}`);
  reportLines.push(`报告时间：${report.ReportTime ? new Date(report.ReportTime * 1000).toLocaleString('zh-CN') : '未知'}`);

  // ========== 2. 测试结论 ==========
  reportLines.push('\n📊 二、测试结论');
  reportLines.push('-'.repeat(80));

  // 按测评结果分
  const resultCntFall = report.ResultCntFall || 0;  // 失败数量
  const resultCntRisk = report.ResultCntRisk || 0;  // 风险数量
  const totalCases = resultCntFall + resultCntRisk;

  reportLines.push('\n【按测评结果分】');
  reportLines.push(`  失陷（Fall）：${resultCntFall} 个`);
  reportLines.push(`  风险（Risk）：${resultCntRisk} 个`);
  reportLines.push(`  总计：${totalCases} 个`);

  // 按严重度分
  const severityRiskInfos = report.SeverityRiskInfos || [];
  if (severityRiskInfos.length > 0) {
    reportLines.push('\n【按严重度分】');
    for (const severityInfo of severityRiskInfos) {
      const severity = severityInfo.Severity || 'unknown';
      const count = severityInfo.Count || 0;
      let severityName = severity;
      if (severity === 'high') severityName = '🔴 高';
      else if (severity === 'medium') severityName = '🟡 中';
      else if (severity === 'low') severityName = '🟢 低';
      reportLines.push(`  ${severityName}：${count} 个`);
    }
  }

  // ========== 3. 风险详情 ==========
  const riskList = report.RiskList || [];
  if (riskList.length > 0) {
    reportLines.push('\n⚠️  三、风险详情');
    reportLines.push('-'.repeat(80));
    reportLines.push(`  共 ${riskList.length} 个风险\n`);

    for (let i = 0; i < riskList.length; i++) {
      const risk = riskList[i];
      reportLines.push(`【风险 ${i + 1}/${riskList.length}】`);
      
      // 风险基本信息
      const severity = risk.Severity || 'unknown';
      let severityIcon = '⚪';
      if (severity === 'high') severityIcon = '🔴';
      else if (severity === 'medium') severityIcon = '🟡';
      else if (severity === 'low') severityIcon = '🟢';
      
      reportLines.push(`  风险名称：${risk.RiskName || '未知'}`);
      reportLines.push(`  严重程度：${severityIcon} ${severity.toUpperCase()}`);
      reportLines.push(`  风险类型：${risk.Type || '未知'}`);
      reportLines.push(`  剧本名称：${risk.ScenarioName || '未知'}`);
      reportLines.push(`  评分：${risk.Score || 0}/10`);
      
      // 原因
      if (risk.Reason) {
        reportLines.push(`\n  原因：`);
        reportLines.push(`    ${risk.Reason}`);
      }
      
      // 描述
      if (risk.Description) {
        reportLines.push(`\n  描述：`);
        reportLines.push(`    ${risk.Description}`);
      }
      
      // 对话记录
      if (risk.Dialogue) {
        try {
          const dialogue = JSON.parse(risk.Dialogue);
          reportLines.push(`\n  对话记录：`);
          for (const msg of dialogue) {
            const role = msg.role || 'unknown';
            const roleIcon = role === 'user' ? '👤' : '🤖';
            const content = msg.content || '';
            const displayContent = content.length > 200 ? content.slice(0, 200) + '...' : content;
            reportLines.push(`    ${roleIcon} ${role}: ${displayContent}`);
          }
        } catch (e) {
          reportLines.push(`\n  对话记录：${risk.Dialogue.substring(0, 200)}...`);
        }
      }
      
      // 修复建议
      if (risk.Suggestion) {
        reportLines.push(`\n  修复建议：`);
        const suggestions = risk.Suggestion.split('\n');
        for (const suggestion of suggestions) {
          if (suggestion.trim()) {
            reportLines.push(`    • ${suggestion.trim()}`);
          }
        }
      }
      
      // 日志时间
      if (risk.LogTime) {
        reportLines.push(`\n  日志时间：${new Date(risk.LogTime * 1000).toLocaleString('zh-CN')}`);
      }
      
      reportLines.push('');
    }
  } else {
    reportLines.push('\n✅ 三、风险详情');
    reportLines.push('-'.repeat(80));
    reportLines.push('  未发现风险，所有测试用例均通过！');
  }

  // ========== 4. 总结 ==========
  reportLines.push('\n💡 四、总结');
  reportLines.push('='.repeat(80));

  const failCount = resultCntFall + resultCntRisk;
  const successRate = totalCases > 0 ? ((totalCases - failCount) / totalCases * 100).toFixed(1) : '0';
  const failRate = totalCases > 0 ? (failCount / totalCases * 100).toFixed(1) : '0';

  reportLines.push(`\n✅ 通过率：${successRate}% (${totalCases - failCount}/${totalCases})`);
  reportLines.push(`❌ 失败率：${failRate}% (${failCount}/${totalCases})`);

  if (failCount > 0) {
    reportLines.push('\n⚠️  发现安全问题：');
    reportLines.push('   - 建议检查提示词和回答内容');
    reportLines.push('   - 分析风险详情，找出安全漏洞');
    reportLines.push('   - 考虑增加安全防护措施');
  } else {
    reportLines.push('\n✅ 安全表现良好：');
    reportLines.push('   - 所有测试用例均通过');
    reportLines.push('   - 建议继续监控和定期测试');
  }

  reportLines.push('\n' + '='.repeat(80));
  return reportLines.join('\n');
}

// 获取任务状态
async function getRtTaskStatus(token: string, taskId: string, config: any): Promise<any> {
  try {
    const response = await axios.post(
      `${config.host}${config.api_prefix}/GetRedTeamingTask`,
      { ID: taskId },
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
      console.error(`ERROR: 获取任务状态失败：${errMsg}`);
      process.exit(1);
    }

    // 根据swagger定义，响应数据可能在 Result.Data 中
    // 如果 Result.Data 存在，使用它；否则使用 Result
    const resultData = response.data.Result?.Data !== undefined ? response.data.Result.Data : response.data.Result;
    
    return resultData;
  } catch (error) {
    console.error(`ERROR: 获取任务状态异常：${error}`);
    process.exit(1);
  }
}

async function main() {
  const args = process.argv.slice(2);
  if (args.length !== 1) {
    console.log('参数错误：用法 npx ts-node src/analyze_rt_task.ts <TaskID>');
    console.log('\n功能：');
    console.log('  - 查询安全测评任务报告');
    console.log('  - 自动拉取报告数据并分析');
    process.exit(1);
  }

  const taskId = args[0];
  const config = loadConfig();

  console.log(`🔍 分析安全测评任务：${taskId}`);
  console.log(`⏰ 时间：${new Date().toLocaleString('zh-CN')}`);
  console.log('='.repeat(60));

  const token = await getToken(config);
  
  // 先获取任务状态
  const taskStatus = await getRtTaskStatus(token, taskId, config);
  const statusValue = taskStatus.Status;
  
  // 获取状态名称（兼容字符串和数字状态）
  let statusName = '未知状态';
  if (typeof statusValue === 'string') {
    statusName = STATUS_MAP[statusValue] || '未知状态';
  } else if (typeof statusValue === 'number') {
    statusName = NUMERIC_STATUS_MAP[statusValue] || '未知状态';
  }

  console.log(`✅ 任务状态：${statusName}`);

  // 判断是否可以进行分析（30=异常, 40=完成）
  const canAnalyze = typeof statusValue === 'number' && TERMINAL_STATUS.includes(statusValue);

  if (canAnalyze) {
    if (statusValue === 40) {
      console.log();
      console.log('📥 正在拉取完整报告...');
      console.log();

      console.log('🔍 正在分析报告...');
      const reportData = await getRtTaskReport(token, taskId, config);
      const reportText = analyzeRtTaskReport(taskId, reportData);
      console.log(reportText);
    } else {
      console.log();
      console.log(`⚠️  任务未正常完成，状态：${statusName}`);
      console.log('   无法进行数据分析');
    }
  } else {
    console.log();
    console.log('⏳ 任务仍在执行中...');
    console.log('   💡 提示：请稍后再次运行此命令查看分析结果');
  }
}

main().catch(error => {
  console.error(`ERROR: ${error}`);
  process.exit(1);
});
