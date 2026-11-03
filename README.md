# 本地 AI 求职工作区

你填一份事实库，AI 只能重组它、不能发明它。红线先筛岗位，七维评分，人工核对投递。零依赖：Python 3.10+，没有包要装。

## 30 秒开始

```bash
git clone https://github.com/ZhimingXUXJTU/job-hunting-helper.git
cd job-hunting-helper
```

在 Claude Code / Codex / OpenCode 等 Agent 里打开这个目录，把下面这段话发给它：

```text
这是我的求职工作区。请先读 .agents/skills/jobhunting/SKILL.md（工作协议）并严格按它执行：
1. 检查 candidate/private/facts.yml 是否存在；不存在就复制 candidate/templates/ 下的三个模板到 candidate/private/，然后逐项问我必要信息，帮我建立事实库，每次最多问 3 个问题。
2. 事实库建好后等我发 JD。我发你 JD 后，按 prompts/02-evaluate-jd.md 评估：先跑 python -X utf8 tools/run_workflow.py --workspace . --jd <JD文件>，再做你的模型复核，报告存到 reports/private/。
纪律：只重组我确认过的事实，缺证据标 [needs_proof]，缺信息标人工复核不要猜，不自动投递，不绕过任何平台限制。
```

这段话会让 Agent：

- 建好你的求职事实库——只记录你确认过的事实，学过的和交付过的分开记
- 加载评估协议，等你投喂第一个 JD
- 之后每份 JD 产出：红线判定、七维评分、简历/开场文案/面试准备草稿

没有装 Agent？看[手动路径](#没有-agent-手动也能跑)，或跟[详细教程](docs/tutorial.md)一步步做。

## 它是什么

三样东西各管一段：

| 文件 | 作用 |
|---|---|
| `candidate/private/facts.yml` | **事实库**：你的真实经历，填一次用到底 |
| `config/scoring.yml` | **规则**：红线 + 七维评分，脚本和 AI 以它为准 |
| `prompts/` | **五条 AI 工作指令**：建库、评估、简历、面试、复盘 |

为什么要这么做：AI 写的简历过得了初筛，过不了面试官的第二个问题——项目细节、预算、上线那晚发生了什么，编不出来。根源是没有事实库，输入残缺，AI 只能替残缺润色。这个工作区让 AI 在事实之内工作，每条简历内容可溯源，缺证据的标 `[needs_proof]`，进不了可投递版本。

## 五个任务，五条指令

| 你要做什么 | 发给 AI 的文件 |
|---|---|
| 建立事实库 | `prompts/01-build-profile.md` |
| 评估一个 JD（先脚本后复核） | `prompts/02-evaluate-jd.md` |
| 生成岗位版简历 + 开场文案 | `prompts/03-tailor-resume.md` |
| 面试准备与追问预测 | `prompts/04-interview.md` |
| 每周复盘 | `prompts/05-weekly-review.md` |

每条指令自带纪律：用词不升级（参与不写成主导）、数字原样搬运、learned 技能永远不写成项目经验、产出自检来源。AI 越界就让它重读指令文件。

## 没有 Agent？手动也能跑

<details>
<summary>展开：命令行 + 复制粘贴的完整路径</summary>

1. 装 Python 3.10+（[python.org](https://www.python.org/downloads/)，Windows 记得勾 Add to PATH）
2. 跑通示例（自带虚构 JD，不用填任何资料）：

   ```bash
   python -X utf8 tools/run_workflow.py --workspace . --jd jobs/inbox/example.json
   ```

3. 把 `candidate/templates/` 的三个文件复制到 `candidate/private/` 填写。要点：`skills` 分 `expert`（能主讲）/ `practiced`（有交付）/ `learned`（学过没交付）三档，拿不准往低放
4. 从招聘网站复制 JD 存进 `jobs/inbox/`（抄 `jobs/templates/jd-template.json`；不会 JSON 就直接丢给 AI 整理）
5. 评估 → 生成材料 → **人工核对每个数字、每个角色** → 手动投递 → 版本号登记进 `applications/private/tracker.csv`

可选：`python -X utf8 tools/dashboard_server.py` 后打开 http://127.0.0.1:8765，一页看全事实库、待评估、投递台账。

</details>

## 调规则

`config/scoring.yml` 是唯一规则文件，改了立即生效：红线黑名单、目标城市、薪资口径（默认按综合年包进评分，低于底线减分不淘汰）、七维权重、80/65 两道档位线。建议先按默认跑两周，攒下"分数高但没回复"的真实案例再调。

## 它不做什么

- 不编造经历、指标、客户、职责
- 不自动发送私信，不自动投递，不自动接受 Offer
- 不绕过登录、验证码、反爬；JD 靠人工复制进本地
- 不上云：真实简历、联系方式、投递记录只在本地 `private/` 目录
- 不承诺 Offer

## 常见问题

<details>
<summary>展开 FAQ</summary>

**中文乱码 / UnicodeEncodeError**
命令带上 `-X utf8`（本文所有命令都带了）。

**用哪个 AI 都行吗？**
行。`prompts/` 是普通文本，任何对话式 AI 都能用；有 Agent 能力（能读文件、跑命令）的体验最好。AI 只知道你发给它的内容，含联系方式的事实库按需给、不必整份发。

**隐私会泄露吗？**
你的真实资料只放 `private/` 目录，`.gitignore` 整体排除，`git add` 加不进去。仓库里出现的公司、人物、数字全部是虚构示例。fork 后想公开自己的仓库，推送前跑 `git status` 确认没有 `private/` 下的真实文件。

**分数 90 却没回复？**
分数只衡量 JD 文本与事实库的重合信号，简历版本、市场、岗位真假都不在分数里。看趋势，不看单点。

**为什么薪资不是一票否决？**
改过一版。现在按综合年包（月薪×薪数）进评分，低于底线减分不淘汰；JD 没写薪资标人工复核，不猜。

</details>

<details>
<summary>目录结构</summary>

```
├── prompts/                    五条 AI 工作指令
├── .agents/skills/jobhunting/  Agent 协议（支持 skills 目录的 AI 自动加载）
├── config/scoring.yml          红线 + 七维评分（唯一规则文件）
├── candidate/templates/        事实库空白模板 → 复制到 candidate/private/ 填写
├── jobs/inbox/                 人工收录的 JD（真实 JD 不上传）
├── applications/templates/     投递台账模板
├── reports|outputs/private/    评估报告与产物（不上传）
├── tools/                      零依赖脚本：评估闭环、本地工作台、受限 YAML 读取器
├── dashboard/                  工作台前端（原生 JS，只读快照）
├── docs/tutorial.md            手把手详细教程
└── tests/                      回归测试（全部虚构数据）
```

</details>

## 来源与许可

工作流参考了 [career-ops-zh](https://github.com/TongyiDai/career-ops-zh) 和 [JobOK](https://github.com/GresonKwan/JobOK)，按中国大陆求职场景做了改造，见 [docs/OPEN_SOURCE_REUSE.md](docs/OPEN_SOURCE_REUSE.md)。本仓库以 [MIT License](LICENSE) 发布。

这个工作区不证明方法能带来 Offer。它做到的是：事实可追溯，每一句都答得上来。
