---
name: jobhunting
description: 本地 AI 求职工作区的 Agent 协议：事实库纪律、评分流程、产物去向。适用于本工作区内的任何求职相关任务（画像、JD 评估、简历定制、面试准备、复盘）。
---

# 求职工作区 Agent 协议

本目录是一个「AI 只能重组、不能发明」的求职事实库工作区。接手任何任务前先读本协议。

## 开工前必读（按序）

1. `candidate/private/facts.yml` —— 事实库（不存在则提示用户先复制模板填写）
2. `config/scoring.yml` —— 红线与七维评分规则（唯一规则来源）
3. `applications/private/tracker.csv` —— 投递台账（了解在途岗位）
4. 需要全量状态时：`python -X utf8 tools/dashboard_server.py` 后读 `http://127.0.0.1:8765/api/snapshot`

## 五条工作指令（对应五类任务）

| 任务 | 指令 |
|---|---|
| 建立画像 | `prompts/01-build-profile.md` |
| 评估 JD | `prompts/02-evaluate-jd.md`（先跑 run_workflow.py，再做模型复核） |
| 定制简历 | `prompts/03-tailor-resume.md` |
| 面试准备 | `prompts/04-interview.md` |
| 每周复盘 | `prompts/05-weekly-review.md` |

接手任务时先读对应指令文件并严格执行其中的纪律。

## 核心纪律（任何任务都适用）

1. **只重组不发明**：产出内容必须能溯源到事实库；无来源的标 `[needs_proof]`，不进入可投递版本。
2. **三档技能不串档**：learned（学习了解）永远不写成项目经验；「参与」不升级「主导」。
3. **数字原样搬运**：不换算口径、不四舍五入夸大。
4. **缺信息标人工复核**，不替用户猜（尤其薪资、时间线）。
5. **写入位置固定**：
   - 评估报告 → `reports/private/<job_id>.md|.json`
   - 岗位材料 → `outputs/private/<job_id>/`
   - 台账 → `applications/private/tracker.csv`（已有 job_id 的行做更新，不重复追加）
   - 事实库本身 → `candidate/private/`
6. **不做的事**：不自动投递、不发私信、不绕过反爬/验证码、不联网抓取招聘平台（JD 由人工复制进 inbox）。
7. **交付即登记**：结果保存后，向用户确认产物路径；聊天里说「做完了」不算完成。

## 工具

- 评估闭环：`python -X utf8 tools/run_workflow.py --workspace . --jd jobs/inbox/<file>.json`
- 回归测试：`python -X utf8 -m unittest discover -s tests`（虚构数据，不碰真实记录）
