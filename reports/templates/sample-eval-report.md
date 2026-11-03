# 评估报告（格式示例 · 虚构数据）

> 真实报告由 `python -X utf8 tools/run_workflow.py --workspace . --jd <file>` 生成，
> 写入 `reports/private/<job_id>.md`；提示词 02 会在此基础上追加「模型复核」一节。

---

# 评估报告 · 虚构网络科技 · Python 后端工程师

- 岗位 ID：fake-normal-20260401
- 城市：上海｜薪资：22k-35k×14
- 来源：https://example.com/jobs/90001
- 评估日期：2026-04-01

## 结论

**总分 94 → advance**

## 七维得分

| 维度 | 得分 | 说明 |
|---|---|---|
| skill_evidence | 100 | JD 硬性要求全部命中 expert/practiced |
| responsibility | 90 | JD 要求 5 年，事实库 5 年 |
| direction | 100 | 命中方向：交易系统、支付、后端架构 |
| salary | 90 | 区间上限覆盖期望 |
| commute | 90 | 上海 ∈ 目标城市 |
| company_risk | 75 | 无公开负面信号（默认分） |
| freshness | 100 | 发布 2 天内 |

## 备注

- [company_risk] 无公开负面信号（默认 75 分；可用天眼查等工具人工核查后再调）

---

规则来源：config/scoring.yml。分数衡量信号，不是录用概率。
投递前请人工核对岗位链接、公司、薪资、地点。
