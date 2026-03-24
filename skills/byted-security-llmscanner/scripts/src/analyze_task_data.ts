import * as fs from 'fs';
import { loadConfig, getTaskDataFile, getReportFile } from './common';

interface TaskResult {
  EvalRiskResult?: number;
  Severity?: string;
  CatalogName?: string;
  OwOspName?: string;
  RiskDesc?: string;
  Question?: string;
  Answer?: string;
  Prompt?: string;
  Response?: string;
}

interface RiskGroup {
  severity: string;
  count: number;
  rate: number;
  cases: TaskResult[];
}

function analyzeTaskData(taskId: string): string {
  const config = loadConfig();
  const dataFile = getTaskDataFile(taskId);

  if (!fs.existsSync(dataFile)) {
    console.error(`ERROR: 未找到任务数据文件 ${dataFile}`);
    process.exit(1);
  }

  const data = JSON.parse(fs.readFileSync(dataFile, 'utf-8'));
  const results: TaskResult[] = data.Data || [];
  const totalCount = results.length;

  if (totalCount === 0) {
    console.error('ERROR: 任务数据为空');
    process.exit(1);
  }

  const riskResults = results.filter(r => r.EvalRiskResult === 1);
  const riskCount = riskResults.length;
  const safeCount = totalCount - riskCount;
  const riskRate = (riskCount / totalCount) * 100;

  const report: string[] = [];

  // 报告头部
  report.push('='.repeat(80));
  report.push('📊 合规测评任务风险分析报告');
  report.push('='.repeat(80));
  report.push(`\n📋 任务ID：${taskId}`);
  report.push(`📊 总测评题数：${totalCount}`);
  report.push(`✅ 安全通过：${safeCount} (${(safeCount / totalCount * 100).toFixed(1)}%)`);
  report.push(`⚠️  发现风险：${riskCount} (${riskRate.toFixed(1)}%)`);

  if (riskCount === 0) {
    report.push('\n✅ 恭喜！本次测评未发现任何风险，模型表现优秀！');
    report.push('\n' + '='.repeat(80));
    return report.join('\n');
  }

  // 按风险等级分组
  const severityGroups = new Map<string, TaskResult[]>();
  const categoryCounter = new Map<string, number>();
  const owaspCounter = new Map<string, number>();

  for (const risk of riskResults) {
    const severity = risk.Severity || 'unknown';
    const category = risk.CatalogName || 'unknown';
    const owasp = risk.OwOspName || 'unknown';

    if (!severityGroups.has(severity)) {
      severityGroups.set(severity, []);
    }
    severityGroups.get(severity)!.push(risk);

    categoryCounter.set(category, (categoryCounter.get(category) || 0) + 1);
    owaspCounter.set(owasp, (owaspCounter.get(owasp) || 0) + 1);
  }

  // 风险等级分布
  report.push('\n' + '='.repeat(80));
  report.push('🚨 风险等级分布');
  report.push('='.repeat(80));

  const severityOrder = ['critical', 'high', 'medium', 'low'];
  const severityEmoji: Record<string, string> = {
    critical: '🔴',
    high: '🟠',
    medium: '🟡',
    low: '🟢',
  };

  for (const severity of severityOrder) {
    const count = severityGroups.get(severity)?.length || 0;
    if (count > 0) {
      const rate = (count / riskCount * 100).toFixed(1);
      report.push(`  ${severityEmoji[severity] || '⚪'} ${severity.toUpperCase().padEnd(8)}：${count} 个 (${rate}%)`);
    }
  }

  // 风险类别分布（TOP 10）
  report.push('\n' + '='.repeat(80));
  report.push('📂 风险类别分布（TOP 10）');
  report.push('='.repeat(80));

  const sortedCategories = Array.from(categoryCounter.entries())
    .sort((a, b) => b[1] - a[1])
    .slice(0, 10);

  for (const [category, count] of sortedCategories) {
    const rate = (count / riskCount * 100).toFixed(1);
    report.push(`  • ${category.padEnd(30)}：${count} 个 (${rate}%)`);
  }

  // 风险类型分布（TOP 10）
  report.push('\n' + '='.repeat(80));
  report.push('🔍 风险类型分布（TOP 10）');
  report.push('='.repeat(80));

  const sortedOwasps = Array.from(owaspCounter.entries())
    .sort((a, b) => b[1] - a[1])
    .slice(0, 10);

  for (const [owasp, count] of sortedOwasps) {
    const rate = (count / riskCount * 100).toFixed(1);
    report.push(`  • ${owasp.padEnd(40)}：${count} 个 (${rate}%)`);
  }

  // 按风险等级详细展示案例
  for (const severity of severityOrder) {
    const cases = severityGroups.get(severity);
    if (!cases || cases.length === 0) continue;

    report.push('\n' + '='.repeat(80));
    report.push(`${severityEmoji[severity] || '⚪'} ${severity.toUpperCase()} 级别风险详情`);
    report.push('='.repeat(80));
    report.push(`  共 ${cases.length} 个案例\n`);

    const displayCases = cases.slice(0, 3); // 每个等级最多显示 3 个
    for (let i = 0; i < displayCases.length; i++) {
      const risk = displayCases[i];
      report.push(`【案例 ${i + 1}/${cases.length}】`);
      report.push(`  风险类别：${risk.CatalogName || 'unknown'}`);
      report.push(`  风险类型：${risk.OwOspName || 'unknown'}`);

      // 风险描述
      const desc = risk.RiskDesc || '无描述';
      if (desc.length > 150) {
        report.push(`  风险描述：${desc.slice(0, 150)}...`);
      } else {
        report.push(`  风险描述：${desc}`);
      }

      // 问题内容（如果有）
      const question = risk.Question || risk.Prompt || '';
      if (question && question.length > 0) {
        const displayQuestion = question.length > 200 ? question.slice(0, 200) + '...' : question;
        report.push(`  问题内容：${displayQuestion}`);
      }

      // 回答内容（如果有）
      const answer = risk.Answer || risk.Response || '';
      if (answer && answer.length > 0) {
        const displayAnswer = answer.length > 200 ? answer.slice(0, 200) + '...' : answer;
        report.push(`  回答内容：${displayAnswer}`);
      }

      report.push('');
    }

    if (cases.length > 3) {
      report.push(`  ... 还有 ${cases.length - 3} 个案例未显示\n`);
    }
  }

  // 风险评估和建议
  report.push('=' .repeat(80));
  report.push('💡 风险评估与建议');
  report.push('='.repeat(80));

  const criticalCount = severityGroups.get('critical')?.length || 0;
  const highCount = severityGroups.get('high')?.length || 0;
  const mediumCount = severityGroups.get('medium')?.length || 0;
  const lowCount = severityGroups.get('low')?.length || 0;

  if (criticalCount > 0) {
    report.push('\n🔴 严重风险（CRITICAL）：');
    report.push('   - 存在严重安全问题，可能导致重大损失');
    report.push('   - 建议：立即修复，暂停相关功能使用');
  }

  if (highCount > 0) {
    report.push('\n🟠 高风险（HIGH）：');
    report.push('   - 存在较高风险，需要尽快处理');
    report.push('   - 建议：在下一个版本中修复');
  }

  if (mediumCount > 0) {
    report.push('\n🟡 中风险（MEDIUM）：');
    report.push('   - 存在一定风险，建议优化');
    report.push('   - 建议：在合适时机进行修复');
  }

  if (lowCount > 0) {
    report.push('\n🟢 低风险（LOW）：');
    report.push('   - 风险较低，可以接受');
    report.push('   - 建议：可以在后续版本中优化');
  }

  report.push('\n' + '='.repeat(80));
  return report.join('\n');
}

function main() {
  const args = process.argv.slice(2);
  if (args.length !== 1) {
    console.log('参数错误：用法 npx ts-node src/analyze_task_data.tsx <TaskID>');
    process.exit(1);
  }

  const taskId = args[0];
  const report = analyzeTaskData(taskId);
  console.log(report);
}

main();
