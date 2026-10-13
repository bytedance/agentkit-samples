#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json
import logging
import os
import re
from datetime import datetime

import yaml

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 脚本所在目录
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
# Skill 根目录（scripts 目录的上一级）
SKILL_ROOT = os.path.dirname(SCRIPT_DIR)

CRM_CONFIG = {
    'data_path': './crm_data.json',
    'backup_enabled': True,
    'max_backups': 5
}

VALID_GENDERS = ['男', '女', '未知']
VALID_INTENTS = ['高', '中', '低']
PHONE_PATTERN = re.compile(r'^1[3-9]\d{9}$')
PHONE_NAME_FILE_PATTERN = re.compile(r'^(1[3-9]\d{9})(?:-([^/\\]+?))?(?:\.(?:mp3|wav|m4a))?$', re.IGNORECASE)


def load_config():
    config_path = os.path.join(SKILL_ROOT, 'config.yaml')
    if not os.path.exists(config_path):
        logger.warning(f"配置文件不存在: {config_path}，使用默认配置")
        return
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        if not config:
            return
        if 'crm' in config:
            CRM_CONFIG.update(config['crm'])
        logger.info("配置文件加载成功")
    except Exception as e:
        logger.warning(f"配置文件加载失败: {e}，使用默认配置")


load_config()


def _get_data_path() -> str:
    data_path = CRM_CONFIG['data_path']
    if not os.path.isabs(data_path):
        data_path = os.path.join(SKILL_ROOT, data_path)
    return data_path


def _load_crm_data() -> dict:
    data_path = _get_data_path()
    if not os.path.exists(data_path):
        return {}
    try:
        with open(data_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        logger.error(f"CRM数据文件读取失败: {e}")
        return {}


def _save_crm_data(data: dict):
    data_path = _get_data_path()

    if CRM_CONFIG.get('backup_enabled') and os.path.exists(data_path):
        _create_backup(data_path)

    os.makedirs(os.path.dirname(data_path) or '.', exist_ok=True)
    with open(data_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    logger.info(f"CRM数据已保存，共{len(data)}条记录")


def _create_backup(data_path: str):
    backup_dir = os.path.join(os.path.dirname(data_path), 'backups')
    os.makedirs(backup_dir, exist_ok=True)

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_path = os.path.join(backup_dir, f"crm_data_{timestamp}.json")

    try:
        with open(data_path, 'r', encoding='utf-8') as src:
            content = src.read()
        with open(backup_path, 'w', encoding='utf-8') as dst:
            dst.write(content)
    except IOError as e:
        logger.warning(f"备份失败: {e}")
        return

    max_backups = CRM_CONFIG.get('max_backups', 5)
    backups = sorted(
        [f for f in os.listdir(backup_dir) if f.startswith('crm_data_') and f.endswith('.json')]
    )
    while len(backups) > max_backups:
        old = backups.pop(0)
        try:
            os.remove(os.path.join(backup_dir, old))
        except IOError:
            pass


def _mask_phone(phone: str) -> str:
    if len(phone) >= 7:
        return phone[:3] + '****' + phone[-4:]
    return phone


def _validate_phone(phone: str) -> bool:
    return bool(phone and PHONE_PATTERN.match(phone))


def _parse_phone_input(phone_input: str) -> tuple[str, str]:
    """解析 phone 参数，兼容纯手机号、手机号-姓名、手机号-姓名.mp3。"""
    value = (phone_input or '').strip()
    if not value:
        return '', ''

    file_name = os.path.basename(value)
    match = PHONE_NAME_FILE_PATTERN.fullmatch(file_name)
    if match:
        phone = match.group(1)
        candidate_name = (match.group(2) or '').strip()
        return phone, candidate_name

    return value, ''


def upsert_candidate(phone: str, **fields) -> str:
    phone, parsed_name = _parse_phone_input(phone)
    if not _validate_phone(phone):
        return f"❌ 电话号码格式无效: {phone}，请提供11位手机号"

    data = _load_crm_data()
    now = datetime.now().strftime('%Y-%m-%d %H:%M')
    is_new = phone not in data

    if is_new:
        record = {
            'phone': phone,
            'candidate_name': '',
            'email': '',
            'is_qualified': False,
            'gender': '未知',
            'industry': '',
            'current_position': '',
            'years_of_exp': None,
            'job_switch_intent': '',
            'candidate_focus': '',
            'notes': '',
            'transcript_text': '',
            'project_experience': '',
            'technical_capability': '',
            'education_level': '',
            'jd_years_match': '',
            'jd_match_score': None,
            'screening_stage': '',
            'screening_decision': '',
            'screening_reason': '',
            'strengths_summary': '',
            'weaknesses_summary': '',
            'final_match_score': None,
            'final_recommendation': '',
            'ai_match_conclusion': '',
            'ai_match_evidence': '',
            'created_at': now,
            'updated_at': now,
            'last_call_date': now[:10]
        }
    else:
        record = data[phone]
        record['updated_at'] = now

    if parsed_name and not record.get('candidate_name'):
        record['candidate_name'] = parsed_name

    if 'candidate_name' in fields and fields['candidate_name']:
        record['candidate_name'] = str(fields['candidate_name']).strip()

    if 'email' in fields and fields['email']:
        record['email'] = str(fields['email']).strip()

    if 'is_qualified' in fields and fields['is_qualified'] is not None:
        record['is_qualified'] = bool(fields['is_qualified'])

    if 'gender' in fields and fields['gender']:
        gender = fields['gender']
        if gender in VALID_GENDERS:
            record['gender'] = gender
        else:
            logger.warning(f"无效性别值: {gender}，保留原值")

    if 'industry' in fields and fields['industry']:
        record['industry'] = str(fields['industry'])

    if 'current_position' in fields and fields['current_position']:
        record['current_position'] = str(fields['current_position'])

    if 'years_of_exp' in fields and fields['years_of_exp'] is not None:
        try:
            years = int(fields['years_of_exp'])
            if 0 <= years < 100:
                record['years_of_exp'] = years
            else:
                logger.warning(f"工作年限超出合理范围: {years}")
        except (ValueError, TypeError):
            logger.warning(f"无效工作年限值: {fields['years_of_exp']}")

    if 'job_switch_intent' in fields and fields['job_switch_intent']:
        intent = fields['job_switch_intent']
        if intent in VALID_INTENTS:
            record['job_switch_intent'] = intent
        else:
            logger.warning(f"无效跳槽意向值: {intent}，保留原值")

    if 'candidate_focus' in fields and fields['candidate_focus']:
        record['candidate_focus'] = str(fields['candidate_focus'])

    if 'notes' in fields and fields['notes']:
        record['notes'] = str(fields['notes'])

    if 'transcript_text' in fields and fields['transcript_text']:
        record['transcript_text'] = str(fields['transcript_text']).strip()

    if 'project_experience' in fields and fields['project_experience']:
        record['project_experience'] = str(fields['project_experience']).strip()

    if 'technical_capability' in fields and fields['technical_capability']:
        record['technical_capability'] = str(fields['technical_capability']).strip()

    if 'education_level' in fields and fields['education_level']:
        record['education_level'] = str(fields['education_level']).strip()

    if 'jd_years_match' in fields and fields['jd_years_match']:
        record['jd_years_match'] = str(fields['jd_years_match']).strip()

    if 'jd_match_score' in fields and fields['jd_match_score'] is not None:
        try:
            score = int(fields['jd_match_score'])
            if 0 <= score <= 100:
                record['jd_match_score'] = score
            else:
                logger.warning(f"JD匹配分超出合理范围: {score}")
        except (ValueError, TypeError):
            logger.warning(f"无效JD匹配分值: {fields['jd_match_score']}")

    if 'screening_stage' in fields and fields['screening_stage']:
        record['screening_stage'] = str(fields['screening_stage']).strip()

    if 'screening_decision' in fields and fields['screening_decision']:
        record['screening_decision'] = str(fields['screening_decision']).strip()

    if 'screening_reason' in fields and fields['screening_reason']:
        record['screening_reason'] = str(fields['screening_reason']).strip()

    if 'strengths_summary' in fields and fields['strengths_summary']:
        record['strengths_summary'] = str(fields['strengths_summary']).strip()

    if 'weaknesses_summary' in fields and fields['weaknesses_summary']:
        record['weaknesses_summary'] = str(fields['weaknesses_summary']).strip()

    if 'final_match_score' in fields and fields['final_match_score'] is not None:
        try:
            score = int(fields['final_match_score'])
            if 0 <= score <= 100:
                record['final_match_score'] = score
            else:
                logger.warning(f"最终匹配分超出合理范围: {score}")
        except (ValueError, TypeError):
            logger.warning(f"无效最终匹配分值: {fields['final_match_score']}")

    if 'final_recommendation' in fields and fields['final_recommendation']:
        record['final_recommendation'] = str(fields['final_recommendation']).strip()

    if 'ai_match_conclusion' in fields and fields['ai_match_conclusion']:
        record['ai_match_conclusion'] = str(fields['ai_match_conclusion']).strip()

    if 'ai_match_evidence' in fields and fields['ai_match_evidence']:
        record['ai_match_evidence'] = str(fields['ai_match_evidence']).strip()

    if 'last_call_date' in fields and fields['last_call_date']:
        record['last_call_date'] = str(fields['last_call_date'])

    data[phone] = record
    _save_crm_data(data)

    masked = _mask_phone(phone)
    action_word = "新增" if is_new else "更新"
    qualified_str = "是" if record['is_qualified'] else "否"
    exp_str = f"{record['years_of_exp']}年" if record['years_of_exp'] is not None else "未知"
    name_str = record.get('candidate_name') or '未知'
    transcript_flag = "已保存" if record.get('transcript_text') else "未保存"
    jd_score_str = (
        f"{record['jd_match_score']}分"
        if record.get('jd_match_score') is not None
        else "未评估"
    )
    final_score_str = (
        f"{record['final_match_score']}分"
        if record.get('final_match_score') is not None
        else "未评估"
    )

    return (
        f"✅ 候选人 {masked} 数据已{action_word}\n"
        f"  姓名: {name_str} | 邮箱: {record.get('email') or '无'} | 有效候选人: {qualified_str}\n"
        f"  性别: {record['gender']} | 行业: {record['industry'] or '未知'} | 职位: {record['current_position'] or '未知'}\n"
        f"  工作年限: {exp_str}\n"
        f"  流程阶段: {record['screening_stage'] or '未设置'} | 初筛结论: {record['screening_decision'] or '未评估'}\n"
        f"  初筛依据: {record['screening_reason'] or '无'}\n"
        f"  跳槽意向: {record['job_switch_intent'] or '未评估'}\n"
        f"  关注重点: {record['candidate_focus'] or '无'}\n"
        f"  项目经验: {record['project_experience'] or '无'}\n"
        f"  技术能力: {record['technical_capability'] or '无'}\n"
        f"  学历水平: {record['education_level'] or '未知'} | 年限匹配: {record['jd_years_match'] or '未评估'} | 匹配分: {jd_score_str}\n"
        f"  候选人优势: {record['strengths_summary'] or '无'}\n"
        f"  候选人劣势: {record['weaknesses_summary'] or '无'}\n"
        f"  最终推荐: {record['final_recommendation'] or '未评估'} | 最终得分: {final_score_str}\n"
        f"  AI结论: {record['ai_match_conclusion'] or '无'}\n"
        f"  AI依据: {record['ai_match_evidence'] or '无'}\n"
        f"  转写原文: {transcript_flag}\n"
        f"  更新时间: {record['updated_at']}"
    )


def query_candidate(phone: str) -> str:
    phone, _ = _parse_phone_input(phone)
    if not _validate_phone(phone):
        return f"❌ 电话号码格式无效: {phone}，请提供11位手机号"

    data = _load_crm_data()
    if phone not in data:
        return f"📋 未找到电话号码 {_mask_phone(phone)} 的候选人档案"

    r = data[phone]
    masked = _mask_phone(phone)
    qualified_str = "是" if r.get('is_qualified') else "否"
    exp_str = f"{r['years_of_exp']}年" if r.get('years_of_exp') is not None else "未知"
    name_str = r.get('candidate_name') or '未知'
    jd_score_str = (
        f"{r['jd_match_score']}分"
        if r.get('jd_match_score') is not None
        else "未评估"
    )
    final_score_str = (
        f"{r['final_match_score']}分"
        if r.get('final_match_score') is not None
        else "未评估"
    )
    transcript_text = r.get('transcript_text') or ''
    transcript_block = (
        f"\n  转写原文:\n{_indent_multiline(transcript_text, '    ')}"
        if transcript_text
        else "\n  转写原文: 无"
    )

    return (
        f"📋 候选人 {masked} 档案\n"
        f"  姓名: {name_str} | 邮箱: {r.get('email') or '无'} | 有效候选人: {qualified_str} | 性别: {r.get('gender', '未知')}\n"
        f"  行业: {r.get('industry') or '未知'} | 职位: {r.get('current_position') or '未知'} | 工作年限: {exp_str}\n"
        f"  流程阶段: {r.get('screening_stage') or '未设置'} | 初筛结论: {r.get('screening_decision') or '未评估'}\n"
        f"  初筛依据: {r.get('screening_reason') or '无'}\n"
        f"  跳槽意向: {r.get('job_switch_intent') or '未评估'}\n"
        f"  关注重点: {r.get('candidate_focus') or '无'}\n"
        f"  项目经验: {r.get('project_experience') or '无'}\n"
        f"  技术能力: {r.get('technical_capability') or '无'}\n"
        f"  学历水平: {r.get('education_level') or '未知'}\n"
        f"  JD年限匹配: {r.get('jd_years_match') or '未评估'} | JD匹配分: {jd_score_str}\n"
        f"  候选人优势: {r.get('strengths_summary') or '无'}\n"
        f"  候选人劣势: {r.get('weaknesses_summary') or '无'}\n"
        f"  最终推荐: {r.get('final_recommendation') or '未评估'} | 最终得分: {final_score_str}\n"
        f"  AI结论: {r.get('ai_match_conclusion') or '无'}\n"
        f"  AI依据: {r.get('ai_match_evidence') or '无'}\n"
        f"  最近通话: {r.get('last_call_date', '无记录')}\n"
        f"  备注: {r.get('notes') or '无'}\n"
        f"  创建时间: {r.get('created_at', '')} | 更新时间: {r.get('updated_at', '')}"
        f"{transcript_block}"
    )


def list_candidates() -> str:
    data = _load_crm_data()
    if not data:
        return "📋 CRM 中暂无候选人数据"

    lines = [f"📋 候选人列表（共 {len(data)} 条记录）\n"]
    for phone, r in sorted(data.items()):
        masked = _mask_phone(phone)
        flag = "🔴" if r.get('is_qualified') else "🟢"
        intent = r.get('job_switch_intent', '')
        position = r.get('current_position', '') or '-'
        industry = r.get('industry', '') or '-'
        name = r.get('candidate_name', '') or '-'
        lines.append(
            f"  {flag} {masked} | {name} | {r.get('email') or '-'} | {r.get('gender', '未知')} | {industry} | {position} | 意向:{intent or '-'}"
        )
    return '\n'.join(lines)


def export_markdown() -> str:
    data = _load_crm_data()
    if not data:
        return "📋 CRM 中暂无候选人数据，无法导出"

    lines = [
        f"### 候选人CRM报表（{datetime.now().strftime('%Y-%m-%d')}）\n",
        "| 电话号码 | 姓名 | 邮箱 | 阶段 | 初筛结论 | 最终推荐 | 有效候选人 | 职位 | 工作年限 | 学历 | JD匹配分 | 最终得分 | 最近通话 |",
        "|----------|------|------|------|----------|----------|-----------|------|---------|------|----------|----------|----------|"
    ]

    qualified_count = 0
    for phone, r in sorted(data.items()):
        masked = _mask_phone(phone)
        is_qualified = r.get('is_qualified', False)
        if is_qualified:
            qualified_count += 1
        qualified_str = "是" if is_qualified else "否"
        exp_str = str(r['years_of_exp']) if r.get('years_of_exp') is not None else "-"
        lines.append(
            f"| {masked} | {r.get('candidate_name') or '-'} | {r.get('email') or '-'} | {r.get('screening_stage') or '-'} | {r.get('screening_decision') or '-'} | "
            f"{r.get('final_recommendation') or '-'} | {qualified_str} | {r.get('current_position') or '-'} | {exp_str} | "
            f"{r.get('education_level') or '-'} | {r.get('jd_match_score') if r.get('jd_match_score') is not None else '-'} | "
            f"{r.get('final_match_score') if r.get('final_match_score') is not None else '-'} | {r.get('last_call_date', '-')} |"
        )

    lines.append(f"\n> 共 {len(data)} 位候选人，其中有效候选人 {qualified_count} 位")
    return '\n'.join(lines)


def _indent_multiline(text: str, prefix: str) -> str:
    return '\n'.join(f"{prefix}{line}" if line else prefix.rstrip() for line in text.splitlines())


def main(action: str, phone: str = '', **kwargs):
    try:
        if action == 'upsert':
            if not phone:
                return "❌ upsert 操作需要提供 phone 参数"
            return upsert_candidate(phone, **kwargs)

        elif action == 'query':
            if not phone:
                return "❌ query 操作需要提供 phone 参数"
            return query_candidate(phone)

        elif action == 'list':
            return list_candidates()

        elif action == 'export':
            return export_markdown()

        else:
            return f"❌ 不支持的操作类型: {action}，可用操作: upsert/query/list/export"

    except Exception as e:
        logger.error(f"CRM操作失败: {str(e)}")
        return f"❌ CRM操作失败: {str(e)}"


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description='候选人CRM数据库管理工具')
    parser.add_argument('--action', required=True,
                        help='操作类型: upsert/query/list/export')
    parser.add_argument('--phone', default='',
                        help='候选人电话号码，兼容 13812341234 / 13812341234-刘 / 13812341234-刘.mp3')
    parser.add_argument('--candidate_name', default=None,
                        help='候选人姓名，未提供时可从文件名中解析')
    parser.add_argument('--email', default=None,
                        help='候选人邮箱，优先从简历文本抽取')
    parser.add_argument('--is_qualified', type=lambda x: x.lower() in ('true', '1', 'yes'),
                        default=None, help='是否为有效候选人')
    parser.add_argument('--gender', default=None,
                        help='候选人性别: 男/女/未知')
    parser.add_argument('--industry', default=None,
                        help='所在行业')
    parser.add_argument('--current_position', default=None,
                        help='当前职位')
    parser.add_argument('--years_of_exp', type=int, default=None,
                        help='工作年限')
    parser.add_argument('--job_switch_intent', default=None,
                        help='跳槽意向: 高/中/低')
    parser.add_argument('--candidate_focus', default=None,
                        help='关注重点')
    parser.add_argument('--notes', default=None,
                        help='备注信息')
    parser.add_argument('--transcript_text', default=None,
                        help='音频转写原文，用于审查留档')
    parser.add_argument('--project_experience', default=None,
                        help='项目经验总结')
    parser.add_argument('--technical_capability', default=None,
                        help='技术能力总结')
    parser.add_argument('--education_level', default=None,
                        help='学历水平，如本科/硕士/博士')
    parser.add_argument('--jd_years_match', default=None,
                        help='工作年限是否符合JD要求，如符合/部分符合/不符合')
    parser.add_argument('--jd_match_score', type=int, default=None,
                        help='JD匹配分，范围0-100')
    parser.add_argument('--screening_stage', default=None,
                        help='流程阶段，如 resume_screened/call_pending/call_completed/final_reviewed')
    parser.add_argument('--screening_decision', default=None,
                        help='初筛结论，如建议沟通/建议补充信息/建议淘汰')
    parser.add_argument('--screening_reason', default=None,
                        help='初筛判断依据')
    parser.add_argument('--strengths_summary', default=None,
                        help='候选人优势总结')
    parser.add_argument('--weaknesses_summary', default=None,
                        help='候选人劣势总结')
    parser.add_argument('--final_match_score', type=int, default=None,
                        help='电话沟通后的最终匹配分，范围0-100')
    parser.add_argument('--final_recommendation', default=None,
                        help='最终推荐结论，如推荐推进/保留观察/不推荐推进')
    parser.add_argument('--ai_match_conclusion', default=None,
                        help='AI 对候选人与JD匹配度的结论')
    parser.add_argument('--ai_match_evidence', default=None,
                        help='AI 判断依据')
    args = parser.parse_args()

    fields = {}
    for key in [
        'candidate_name', 'is_qualified', 'gender', 'industry', 'current_position',
        'email',
        'years_of_exp', 'job_switch_intent', 'candidate_focus', 'notes',
        'transcript_text', 'project_experience', 'technical_capability',
        'education_level', 'jd_years_match', 'jd_match_score',
        'screening_stage', 'screening_decision', 'screening_reason',
        'strengths_summary', 'weaknesses_summary', 'final_match_score',
        'final_recommendation',
        'ai_match_conclusion', 'ai_match_evidence'
    ]:
        val = getattr(args, key)
        if val is not None:
            fields[key] = val

    result = main(args.action, args.phone, **fields)
    print(result)
