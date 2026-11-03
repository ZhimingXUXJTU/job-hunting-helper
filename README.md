# 本地 AI 求职工作区

> AI 只使用你确认过的事实。

AI 写的简历能过初筛，过不了面试官的第二个问题。

项目怎么立项，预算怎么分，上线那晚出了什么问题——这些细节 AI 编不出来。你答不上来，就结束了。

下面这些都真实发生过：

- “参与”被升级成“主导”，供应商做的系统写成了你开发的
- “了解 RAG”变成“有 RAG 工程经验”，学过的和交付过的，面试官分得清
- 估算被写成实测，公司评级变成个人战绩
- 简历改到第 13 版，投递记录里还挂着第 1 版
- 同一个项目，三个文件里三种起止时间

根源多数不是 AI，是没有事实库。输入是残缺的，AI 写得再好，也只是替残缺润色。

这个工作区就是那个事实库：本地文件结构，一套 AI 工作协议，一圈让它只能重组、不能发明的规矩。这些规矩不是设计出来的，是一次次核对里长出来的。

不需要数据库，不需要装依赖，不需要注册任何服务。会复制粘贴就能用。

---

## 工作原理

```
事实库 → 岗位收集 → 规则评估 → AI 复核 → 人工核对 → 投递 → 面试 → 复盘
```

三样东西各管一段：

1. **事实库**（你填一次，之后一直用）：`candidate/private/facts.yml`，记录你真实做过的事
2. **规则**（一份配置文件）：`config/scoring.yml`，红线 + 七维评分，脚本和 AI 都以它为准
3. **AI**（五条工作指令）：`prompts/` 目录，每条是一段可以直接发给 AI 的完整任务书

AI 做提炼、评估、改写。核对、决定、提交，由你完成。

---

## 5 分钟跑通示例（不用填任何资料）

仓库自带一份虚构示例（示例科技 · Python 后端工程师），跑一遍就能看到全部产物。

### 第 0 步：确认 Python

打开终端（Windows 按 `Win+R`，输入 `cmd` 回车；Mac 打开“终端”），输入：

```
python --version
```

- 显示 `3.10` 或更高 → 直接进行第 1 步
- 报错或版本低于 3.10 → 去 [python.org/downloads](https://www.python.org/downloads/) 下载安装。**Windows 安装时勾选 "Add Python to PATH"**，装完重开终端再验证

### 第 1 步：拿到仓库

两种方式任选：

```
git clone https://github.com/ZhimingXUXJTU/job-hunting-helper.git
```

或者：GitHub 页面点绿色的 **Code** 按钮 → **Download ZIP** → 解压到任意目录。

### 第 2 步：进入目录，跑一条命令

```
cd <仓库目录>
python -X utf8 tools/run_workflow.py --workspace . --jd jobs/inbox/example.json
```

`-X utf8` 是让 Windows 正确显示中文，Mac/Linux 也可以带着它。

### 第 3 步：看产物

命令会列出它写了哪些文件，都在 `private/` 目录（你的真实资料以后也放这里，不会被上传）：

| 文件 | 内容 |
|---|---|
| `reports/private/example-20260401-backend.md` | 评估报告：红线判定、七维得分、总分结论 |
| `outputs/private/example-20260401-backend/resume-draft.md` | 简历草稿（虚构示例资料重组出来的） |
| `outputs/private/example-20260401-backend/outreach.md` | 开场文案骨架 |
| `outputs/private/example-20260401-backend/interview-prep.md` | 面试准备 |
| `applications/private/tracker.csv` | 投递台账，多了一行示例记录 |

用记事本或任何编辑器打开评估报告看一遍——它就是后面每一步的核心产物。

不想跑命令？也可以先只读文档，把仓库丢给任意 AI（见下面第四步）。

---

## 第一步：填你自己的事实库

把 `candidate/templates/` 里的三个文件复制到 `candidate/private/`，然后填写：

```
candidate/templates/facts.yml     → candidate/private/facts.yml
candidate/templates/profile.md    → candidate/private/profile.md
candidate/templates/projects.md   → candidate/private/projects.md
```

三个文件分工：`facts.yml` 给脚本读（结构化），`profile.md` 给人和 AI 读（叙述），`projects.md` 是每个项目的证据卡片。时间、数字以 facts.yml 为唯一版本。

### facts.yml 怎么填

**basics（基本情况）**：只写发生过的事实。姓名和联系方式填在这里，它们只存在你电脑上，不会被上传（原因见[隐私设计](#隐私设计)）。

**preferences（求职条件）**：

```yaml
salary_floor_k: 18      # 月薪底线（千元，税前）。低于它只减分，不淘汰
salary_expect_k: 25     # 期望月薪。达到期望加分
cities: [上海, 杭州]     # 目标城市。不在列表里的岗位直接淘汰
directions: [交易系统, 支付]   # 想做的业务方向关键词，用于匹配打分
non_negotiables: [大小周]      # 其他不可接受的条件
```

**skills（三档技能，最重要的设计）**：

| 档 | 什么算 | 例子 |
|---|---|---|
| `expert` | 能扛住面试官连环追问、可以主讲方案 | 你做了三年的东西 |
| `practiced` | 有完整交付记录，但不是你最深的方向 | 项目里用过、上线过 |
| `learned` | 看过课、读过文档、跑过 demo，没有真实交付 | RAG、Kubernetes |

规矩只有一条：**learned 永远不会被写成项目经验**。评分脚本碰到 JD 要求 learned 技能时只标记差距；AI 生成简历时 learned 只出现在“学习与关注”栏。这条规则同时写在了脚本和提示词里，不靠自觉。

拿不准归哪档？往低放。放进 learned 损失一点分数，放高了损失一场面试。

**experience 和 projects（经历与项目）**：

- `role` 三选一：主导 / 参与 / 支持。当时是参与就写参与，AI 不许升级
- `metrics` 里的每个数字都要写来源（面板截图、周报、邮件）。写不出来源的，挪到 `status: needs_proof`
- `evidence` 写证据在哪，比如“周报截图”“代码仓链接”

### profile.md 和 projects.md 怎么填

照着模板里的注释逐段填。两份模板里所有灰色说明都可以在填完后删掉。填不出来的字段空着，比编一个强。

---

## 第二步：收一个真实岗位

从招聘网站把 JD 完整复制下来（标题、薪资、城市、职责、要求），存成 JSON 放进 `jobs/inbox/`。

不会写 JSON？两个办法：

1. 抄 `jobs/templates/jd-template.json`，把引号里的内容换成你的。注意 JSON 里换行要写成 `\n`
2. 更简单：把 JD 原文直接丢给 AI，附一句——

> 请把这份 JD 按我仓库里 jobs/templates/jd-template.json 的格式整理成 JSON，拿不准的字段留空，不要猜。薪资按 JD 原文填，不要换算。

文件名建议 `YYYYMMDD-公司-岗位.json`。`id` 字段起个不含中文的短名，比如 `20260401-acme-backend`——它会成为所有产物的文件名。

---

## 第三步：评估

### 先跑脚本

```
python -X utf8 tools/run_workflow.py --workspace . --jd jobs/inbox/20260401-acme-backend.json
```

脚本不联网、不调用任何模型，只做规则计算：红线判定 → 七维打分 → 生成草稿。

### 再让 AI 复核

脚本算得出关键词重合，看不懂“这个团队水平如何”“JD 里藏着加班暗示”。所以第二步是让 AI 补判断。

把整份 `prompts/02-evaluate-jd.md` 的内容、评估报告内容、JD 原文一起发给任意 AI（Claude、ChatGPT、通义、Kimi 都行），或者更省事：

> 我把仓库目录交给你。请读 `.agents/skills/jobhunting/SKILL.md` 和 `prompts/02-evaluate-jd.md`，按里面的流程评估 `jobs/inbox/` 里的这份新 JD：先跑脚本，再做模型复核，把复核写进报告。遵守文件里的所有纪律。

AI 会给出它的独立评分和理由。**它和脚本分数不一致时两份都保留**，这正是要的效果——分歧的地方就是需要你人看的地方。

### 报告怎么读

- **红线（eliminated）**：命中即淘汰，不用看分数了
- **七维得分**：每维 0-100 分，看低分的 note 列——它说了扣分原因
- **总分档位**：≥80 重点推进；≥65 人工复核；再往下观察或放弃
- **manual_review（人工复核标记）**：JD 没写薪资、没写城市这类信息缺失。脚本不猜，你补
- **needs_proof**：事实库里没有证据支撑的内容。处理掉之前，进不了可投递版本

分数衡量的是信号强度，不是录用概率。

---

## 第四步：生成材料，人工核对后投递

对决定投递的岗位，把 `prompts/03-tailor-resume.md` + 事实库 + 评估报告发给 AI，产出岗位版简历、修改说明、开场文案。

**AI 给的是草稿，不是成品。** 投递前逐行核对三样东西：

1. 每个数字和事实库一致（原样搬运，没有被夸大）
2. 每个项目角色没被升级（参与还是参与）
3. 所有 `[needs_proof]` 标记都已处理或删除

核对完把版本号（比如 `v2`）填进 `applications/private/tracker.csv` 的 `resume_version` 列——以后随时能回答“这家公司投的是哪一版”。

然后在招聘网站**手动**投递。这个工作区没有、也不会有自动投递功能。

---

## 第五步：面试与复盘

面试前把 `prompts/04-interview.md` 和定稿简历发给 AI，生成追问预测。它预测的是问题，不是答案——答案只能来自你的事实库。答不上来的问题记下来，面试后回填事实库，这是下一轮迭代的输入。

每周把 `prompts/05-weekly-review.md` 发给 AI 做一次复盘：数投递漏斗、清 needs_proof 存量、看评分规则要不要调。

---

## 可选：本地工作台

```
python -X utf8 tools/dashboard_server.py
```

浏览器打开 http://127.0.0.1:8765，一页看全：事实库状态、待评估 JD、评估结果、投递台账、当前规则。只读展示，数据直接来自本地文件，只绑定本机回环地址，页面不联网。

---

## 调整评分规则

`config/scoring.yml` 是唯一规则文件，改了立即生效，不用重启任何东西：

- **redlines**：用工形式黑名单、目标城市、骗局关键词（培训费、押金这类）。一条命中即淘汰
- **salary_notes**：薪资口径。默认按综合年包（月薪×薪数）进评分，低于底线减分不淘汰；JD 没写薪资标人工复核
- **dimensions**：七个维度的权重，加起来保持 100
- **thresholds**：80/65 两道档位线

改规则的建议先写在每周复盘里，跑过几周再动。规则改频繁，分数就失去参考意义。

---

## 它不做什么

- 不编造经历、指标、客户、职责
- 不自动发送私信，不自动投递，不自动接受 Offer
- 不绕过登录、验证码、反爬；JD 靠人工复制、截图和公开页面进入本地
- 不上云：真实简历、联系方式、投递记录只在本地 `private/` 目录
- 不承诺 Offer

---

## 目录结构

```
├── README.md                      本文件
├── LICENSE                        MIT 许可证
├── .agents/skills/jobhunting/     Agent 协议（支持 skills 目录的 AI 直接读取）
├── prompts/                       五条工作指令（发给 AI 的完整任务书）
│   ├── 01-build-profile.md        建立事实库
│   ├── 02-evaluate-jd.md          评估岗位（先脚本后 AI 复核）
│   ├── 03-tailor-resume.md        定制简历与开场文案
│   ├── 04-interview.md            面试准备
│   └── 05-weekly-review.md        每周复盘
├── config/scoring.yml             红线 + 七维评分（唯一规则文件）
├── candidate/
│   ├── templates/                 事实库空白模板（复制到 private/ 填写）
│   └── private/                   你的真实资料（不上传）
├── jobs/
│   ├── inbox/                     人工收录的 JD（真实 JD 不上传）
│   └── templates/                 JD 的 JSON 格式模板
├── applications/
│   ├── templates/                 投递台账模板
│   └── private/                   你的 tracker.csv（不上传）
├── reports/
│   ├── templates/                 评估报告格式示例（虚构）
│   └── private/                   评估报告（不上传）
├── outputs/
│   ├── templates/                 产物格式示例（虚构）
│   └── private/                   简历草稿、文案、面试准备（不上传）
├── tools/                         零依赖 Python 脚本
│   ├── run_workflow.py            评估闭环（红线过滤 + 七维评分 + 四件产物）
│   ├── dashboard_server.py        本地工作台
│   └── mini_yaml.py               受限 YAML 读取器（免去装 PyYAML）
├── dashboard/                     工作台前端（原生 JS）
├── docs/OPEN_SOURCE_REUSE.md      参考的开源项目与改造说明
└── tests/                         回归测试（全部虚构数据）
```

---

## 隐私设计

- 所有你的真实资料只放 `private/` 目录，`.gitignore` 整体排除，`git add` 加不进去
- 仓库里出现的公司、人物、数字全部是虚构示例，和任何真实企业无关
- 联系方式只写在 `candidate/private/facts.yml`，脚本产物里永远不会出现（简历草稿里是占位符，投递时你自己填）
- 工作台只绑定 127.0.0.1，同一台电脑之外访问不到

**如果你 fork 或改完想公开自己的仓库**，推送前跑一次：

```
git status
```

输出里不应该出现任何 `private/` 下的真实文件名。再检查一遍：真实 JD 不要存进 `jobs/inbox/` 后直接提交（该目录整体被忽略，只留了虚构示例）。

---

## 常见问题

**中文乱码 / UnicodeEncodeError**
命令带上 `-X utf8`（本文所有命令都带了）。这是 Windows 默认编码导致的，Mac/Linux 一般不会遇到。

**必须会用命令行吗？**
只会一条：`cd` 进目录，然后粘贴命令。所有命令都在本文里，复制即可。

**必须装 Git 吗？**
不用。Download ZIP 解压一样用。Git 只在你以后想拉取更新时才需要。

**用哪个 AI 都行吗？**
行。`prompts/` 里的指令是普通文本，任何能读长文本的对话式 AI 都能用。有 Agent 能力（能读本地文件、跑命令）的 AI 体验最好——把仓库目录交给它，让它读 `.agents/skills/jobhunting/SKILL.md` 开始。没有 Agent 能力就手动复制文件内容给它。

**AI 会不会把我的资料发到网上？**
AI 只知道你发给它的内容。你不发，它不知道。含联系方式和完整经历的 `facts.yml`，按需给：让 AI 评估岗位时，发条件与技能部分就够了，不必整份都发。

**分数 90 却没回复，为什么？**
分数只衡量 JD 文本和你事实库的重合信号。简历版本、市场、岗位真假都不在分数里。复盘时看趋势，不要看单点。

**能改规则吗？**
能，`config/scoring.yml` 就是为改而设计的。但建议先按默认规则跑两周，攒下“分数高但没回复”的真实案例再调——那时你知道该调哪一维。

---

## 来源与许可

工作流参考了 [career-ops-zh](https://github.com/TongyiDai/career-ops-zh) 和 [JobOK](https://github.com/GresonKwan/JobOK)，按中国大陆求职场景做了改造。参考了什么、改了什么，见 `docs/OPEN_SOURCE_REUSE.md`。

本仓库以 [MIT License](LICENSE) 发布。

这个工作区不证明方法能带来 Offer。它做到的是：事实可追溯，每一句都答得上来。
