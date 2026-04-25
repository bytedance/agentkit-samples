# 评估结果 Schema

AI 在读取 `bundle.json` 后，应输出一个 `assessment.json`。

## 单候选人结构

推荐结构如下：

```json
{
  "phone": "13999999999",
  "candidate_name": "刘女士",
  "email": "liu@example.com",
  "is_qualified": true,
  "screening_stage": "resume_screened",
  "screening_decision": "建议沟通",
  "screening_reason": "核心技术栈与 JD 高度相关，项目经验匹配度较高。",
  "strengths_summary": "后端架构经验扎实，做过高并发与消息队列项目。",
  "weaknesses_summary": "当前跳槽意愿一般，录音中表达了稳定诉求。",
  "gender": "女",
  "industry": "互联网",
  "current_position": "高级后端工程师",
  "years_of_exp": 8,
  "job_switch_intent": "中",
  "candidate_focus": "薪资、团队稳定性、远程办公",
  "notes": "录音中表示当前工作稳定，但可长期保持联系。",
  "transcript_text": "完整通话转写原文",
  "project_experience": "负责支付网关、风控平台、微服务治理等项目。",
  "technical_capability": "Java、Spring Cloud、MySQL、Kafka、云原生部署。",
  "education_level": "本科",
  "jd_years_match": "符合",
  "jd_match_score": 78,
  "final_match_score": 74,
  "final_recommendation": "建议推进一面",
  "ai_match_conclusion": "整体匹配度较高，技术栈与项目背景较贴近 JD。",
  "ai_match_evidence": "简历显示 8 年后端经验，项目中使用微服务与消息队列；录音中候选人关注稳定性且暂无强烈跳槽意愿。",
  "last_call_date": "2026-04-25"
}
```

## 多候选人批量结构

```json
{
  "candidates": [
    {
      "phone_source": "13999999999-刘女士.mp3",
      "candidate_name": "刘女士",
      "screening_stage": "resume_screened",
      "screening_decision": "建议沟通",
      "screening_reason": "..."
    }
  ]
}
```

## 字段原则

- `phone` 是全局唯一 key，初筛建档时应来自简历文本抽取结果，通话后更新也必须使用同一个手机号
- `email` 建议来自简历文本抽取结果，用于后续邮件邀约复试
- `screening_stage` 推荐值：`resume_screened` / `call_pending` / `call_completed` / `final_reviewed`
- `screening_decision` 推荐值：`建议沟通` / `建议补充信息` / `建议淘汰`
- `screening_reason` 说明为何给出初筛结论
- `strengths_summary` / `weaknesses_summary` 必须概括候选人优劣势
- `transcript_text` 必须保留原始转写全文，供后续审查，不能写成摘要版
- `project_experience` 总结既往项目经历，强调与 JD 相关的项目
- `technical_capability` 总结技术栈、系统能力、工程能力
- `education_level` 只写从简历或对话中明确得到的学历
- `jd_years_match` 推荐值：`符合` / `部分符合` / `不符合` / `待确认`
- `jd_match_score` 建议为 `0-100` 整数
- `final_match_score` 建议为电话沟通后的最终分，范围 `0-100`
- `final_recommendation` 推荐值：`建议推进` / `保留观察` / `不推荐推进`
- `ai_match_conclusion` 给出一句总结性判断
- `ai_match_evidence` 必须写出依据来源，区分“简历信息”和“通话信息”
