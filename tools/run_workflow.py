#!/usr/bin/env python3
"""一条命令跑通「评估到产物」的闭环（零依赖，Python 3.10+）。

用法：
    python -X utf8 tools/run_workflow.py --workspace . --jd jobs/inbox/example.json

流程：先红线过滤，再七维评分；产出评估报告、简历草稿、开场文案、
面试准备，并更新 tracker。缺薪资底线、工时制度等信息时保留为人工复核，
不替人猜。本脚本不调用任何模型，只做规则计算与事实重组：
草稿里每一行内容都来自 candidate/private/facts.yml，无来源的内容
一律标注 [needs_proof]。
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from mini_yaml import load_file  # noqa: E402

TRACKER_HEADER = [
    "collected_date", "job_id", "company", "position", "city",
    "salary_min_k", "salary_max_k", "score", "verdict", "status",
    "resume_version", "source_url", "next_action", "notes",
]

RISK_KEYWORDS = ["仲裁", "裁员", "经营异常", "失信", "被执行"]


# ---------------------------------------------------------------- 基础读取

def load_json(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def _as_list(v) -> list:
    if v is None:
        return []
    return v if isinstance(v, list) else [v]


def load_facts(workspace: Path) -> dict | None:
    path = workspace / "candidate" / "private" / "facts.yml"
    if not path.exists():
        return None
    return load_file(path)


# ---------------------------------------------------------------- 红线

def check_redlines(jd: dict, facts: dict | None, rules: dict) -> dict:
    """返回 {eliminated: bool, reasons: [], manual_review: []}。"""
    res = {"eliminated": False, "reasons": [], "manual_review": []}
    rl = rules.get("redlines") or {}

    etype = (jd.get("employment_type") or "").strip()
    if not etype:
        res["manual_review"].append("JD 未写用工形式，默认按全职处理，请人工确认")
    blocked_types = _as_list(rl.get("employment_type_blocked"))
    prefs = (facts or {}).get("preferences") or {}
    blocked_types += _as_list(prefs.get("employment_type_blocked"))
    if etype and any(w in etype for w in blocked_types):
        res["eliminated"] = True
        res["reasons"].append(f"用工形式命中红线：{etype}")

    for kw in _as_list(rl.get("keyword_blocked")):
        if kw and kw in (jd.get("jd_text") or ""):
            res["eliminated"] = True
            res["reasons"].append(f"JD 文本命中红线关键词：{kw}")

    cities = [c for c in _as_list(rl.get("cities_allowed")) if c]
    if cities:
        city = (jd.get("city") or "").strip()
        if not city:
            res["manual_review"].append("JD 未写城市，红线城市判定待人工确认")
        elif not any(city.startswith(c) or c in city for c in cities):
            res["eliminated"] = True
            res["reasons"].append(f"城市不在允许列表：{city}")

    # 薪资不是红线（2026-11 调整）：低于底线在评分的 salary 维度减分，这里
    # 只处理「JD 未写薪资」这种信息缺失，保留人工复核，不猜。
    sal = jd.get("salary") or {}
    if not sal.get("min_k") and not sal.get("max_k"):
        res["manual_review"].append("JD 未写薪资，薪资维度按 0 分计，保留人工复核")
    return res


# ---------------------------------------------------------------- 七维评分

def _skill_universe(facts: dict) -> dict[str, set[str]]:
    skills = (facts.get("skills") or {})
    return {
        "expert": {s.lower() for s in _as_list(skills.get("expert")) if s},
        "practiced": {s.lower() for s in _as_list(skills.get("practiced")) if s},
        "learned": {s.lower() for s in _as_list(skills.get("learned")) if s},
    }


def _score_skill_evidence(jd_text: str, facts: dict, note: list) -> int:
    uni = _skill_universe(facts)
    if not (uni["expert"] | uni["practiced"] | uni["learned"]):
        note.append("skills 未填写，技能证据按缺省 40 分 + 人工复核")
        return 40
    text = jd_text.lower()
    required = {s for s in (uni["expert"] | uni["practiced"] | uni["learned"]) if s in text}
    if not required:
        note.append("JD 未提到清单内任何技能，覆盖度无法计算，按 60 分 + 人工复核")
        return 60
    deliverable = uni["expert"] | uni["practiced"]
    covered = required & deliverable
    ratio = len(covered) / len(required)
    base = round(ratio * 100)
    if required & uni["learned"]:
        note.append(
            f"JD 提到仅学习过（learned，非实操）的技能：{sorted(required & uni['learned'])}；"
            "这些不会计为项目经验，仅在此提示差距")
    return base


def _score_responsibility(jd_text: str, facts: dict, note: list) -> int:
    years = facts.get("basics", {}).get("years_of_experience")
    want = None
    m = re.search(r"(\d+)\s*年", jd_text)
    if m:
        want = int(m.group(1))
    score = 70
    if isinstance(years, int) and want is not None:
        if years >= want:
            score = 90
        elif years >= want - 1:
            score = 70
        else:
            score = 40
            note.append(f"JD 要求约 {want} 年经验，事实库记录 {years} 年")
    else:
        note.append("年限对比信息不全（facts 缺年限或 JD 未写年限），按 70 分基础 + 人工复核")
    senior_words = ["主导", "负责", "架构", "带教", "评审"]
    hits = [w for w in senior_words if w in jd_text]
    if len(hits) >= 3:
        score = min(100, score + 5)
        note.append(f"JD 职责含高层级词 {hits[:3]}，+5")
    return score


def _score_direction(jd_text: str, facts: dict, note: list) -> int:
    dirs = _as_list((facts.get("preferences") or {}).get("directions"))
    if not dirs:
        note.append("preferences.directions 未填写，方向维度按 60 分 + 人工复核")
        return 60
    hits = [d for d in dirs if str(d) in jd_text]
    if not hits:
        return 50
    return min(100, 50 + round(len(hits) / len(dirs) * 50))


def _score_salary(jd: dict, facts: dict, note: list) -> int:
    """薪资只影响评分，不作一票否决；按综合年包（月薪×薪数）口径判断。"""
    prefs = facts.get("preferences") or {}
    floor = prefs.get("salary_floor_k")
    expect = prefs.get("salary_expect_k")
    sal = jd.get("salary") or {}
    if not sal.get("min_k") and not sal.get("max_k"):
        note.append("JD 未写薪资，薪资维度 0 分 + 人工复核")
        return 0
    mx = sal.get("max_k") or sal.get("min_k")
    mn = sal.get("min_k") or mx
    if not isinstance(mx, (int, float)):
        note.append("薪资字段无法解析，按 30 分 + 人工复核")
        return 30
    months = sal.get("months")
    if isinstance(months, (int, float)) and months:
        note.append(f"按综合年包口径：{mn}k-{mx}k × {months} 薪")
    if isinstance(expect, (int, float)) and mn >= expect:
        return 100
    if isinstance(expect, (int, float)) and mx >= expect:
        return 90
    if isinstance(floor, (int, float)) and mn >= floor:
        return 80
    if isinstance(floor, (int, float)) and mx >= floor:
        return 65
    if isinstance(floor, (int, float)):
        note.append(f"薪资 {mn}k-{mx}k 低于事实库底线 {floor}k；只减分，不构成一票否决")
    else:
        note.append(f"薪资 {mn}k-{mx}k 低于事实库的期望与底线；只减分，不构成一票否决")
    return 30


def _score_commute(jd: dict, facts: dict, note: list) -> int:
    cities = _as_list((facts.get("preferences") or {}).get("cities"))
    city = (jd.get("city") or "").strip()
    if not cities:
        note.append("目标城市未配置，通勤维度按 60 分 + 人工复核")
        return 60
    if city and any(city.startswith(c) or c in city for c in cities):
        return 90
    return 40


def _score_company_risk(jd: dict, note: list) -> int:
    score = 75
    risks = _as_list(jd.get("risk_notes"))
    text = jd.get("jd_text") or ""
    hits = [w for w in RISK_KEYWORDS if w in text]
    if risks:
        score -= 25 * len(risks)
        note.append(f"JD 录入时已标风险：{risks}")
    if hits:
        score -= 25 * len(hits)
        note.append(f"JD 文本出现风险词：{hits}")
    if not risks and not hits:
        note.append("无公开负面信号（默认 75 分；可用天眼查等工具人工核查后再调）")
    return max(0, score)


def _score_freshness(jd: dict, today: date, note: list) -> int:
    raw = jd.get("published_at")
    if not raw:
        note.append("JD 未写发布时间，新鲜度 0 分 + 人工复核")
        return 0
    try:
        pub = datetime.strptime(str(raw), "%Y-%m-%d").date()
    except ValueError:
        note.append(f"发布时间无法解析：{raw!r}，新鲜度 0 分 + 人工复核")
        return 0
    days = (today - pub).days
    for limit, sc in ((7, 100), (14, 85), (30, 70), (60, 50)):
        if days <= limit:
            return sc
    note.append(f"发布已 {days} 天（超过 60 天按 25 分），岗位可能已关闭，投递前确认")
    return 25


def evaluate(jd: dict, facts: dict | None, rules: dict, today: date) -> dict:
    facts = facts or {}
    redline = check_redlines(jd, facts, rules)
    notes: list[str] = list(redline["manual_review"])
    dims: dict[str, dict] = {}

    if redline["eliminated"]:
        for name in rules.get("dimensions", {}):
            dims[name] = {"score": 0, "note": "红线淘汰，未评分"}
        total = 0
        verdict = "eliminated"
    else:
        text = jd.get("jd_text") or ""
        scorers = {
            "skill_evidence": lambda n: _score_skill_evidence(text, facts, n),
            "responsibility": lambda n: _score_responsibility(text, facts, n),
            "direction": lambda n: _score_direction(text, facts, n),
            "salary": lambda n: _score_salary(jd, facts, n),
            "commute": lambda n: _score_commute(jd, facts, n),
            "company_risk": lambda n: _score_company_risk(jd, n),
            "freshness": lambda n: _score_freshness(jd, today, n),
        }
        dim_rules = rules.get("dimensions") or {}
        weighted = 0
        for name, rule in dim_rules.items():
            notes_dim: list[str] = []
            score = scorers[name](notes_dim)
            dims[name] = {"score": score, "note": "; ".join(notes_dim)}
            notes.extend(f"[{name}] {m}" for m in notes_dim)
            weighted += score * (rule.get("weight") or 0)
        total = round(weighted / 100)
        th = rules.get("thresholds") or {}
        if total >= (th.get("advance") or 80):
            verdict = "advance"
        elif total >= (th.get("review") or 65):
            verdict = "review"
        elif total >= 50:
            verdict = "watch"
        else:
            verdict = "pass"

    return {
        "job_id": jd.get("id") or "",
        "company": jd.get("company") or "",
        "position": jd.get("position") or "",
        "city": jd.get("city") or "",
        "salary": jd.get("salary") or {},
        "source_url": jd.get("source_url") or "",
        "evaluated_at": today.isoformat(),
        "redline": redline,
        "dimensions": dims,
        "total": total,
        "verdict": verdict,
        "notes": notes,
        "data_incomplete": bool(redline["manual_review"]) or any(
            "manual_review" in d.get("note", "") or "人工复核" in d.get("note", "")
            for d in dims.values()
        ),
    }


# ---------------------------------------------------------------- 产物生成

def _fmt_sal(sal: dict) -> str:
    if not sal.get("min_k") and not sal.get("max_k"):
        return "未写（人工确认）"
    months = f"×{sal['months']}" if sal.get("months") else ""
    return f"{sal.get('min_k', '?')}k-{sal.get('max_k', '?')}k{months}"


def render_report_md(res: dict, jd: dict) -> str:
    lines = [
        f"# 评估报告 · {jd.get('company', '')} · {jd.get('position', '')}",
        "",
        f"- 岗位 ID：{res['job_id']}",
        f"- 城市：{res.get('city') or '未写'}｜薪资：{_fmt_sal(res.get('salary') or {})}",
        f"- 来源：{res.get('source_url') or '未记录'}",
        f"- 评估日期：{res['evaluated_at']}",
        "",
        "## 结论",
        "",
        f"**总分 {res['total']} 分 → {res['verdict']}**"
        + ("（数据不全，仅供粗筛）" if res["data_incomplete"] else ""),
        "",
    ]
    rl = res["redline"]
    if rl["reasons"]:
        lines += ["红线（一条命中即淘汰）："] + [f"- {r}" for r in rl["reasons"]] + [""]
    if rl["manual_review"]:
        lines += ["待人工确认："] + [f"- {r}" for r in rl["manual_review"]] + [""]
    lines += ["## 七维得分", "", "| 维度 | 得分 | 说明 |", "|---|---|---|"]
    for name, d in res["dimensions"].items():
        lines.append(f"| {name} | {d['score']} | {d['note']} |")
    lines += ["", "## 备注", ""]
    lines += [f"- {n}" for n in res["notes"]] or ["- 无"]
    lines += [
        "",
        "---",
        "规则来源：config/scoring.yml。分数衡量信号，不是录用概率。",
        "投递前请人工核对岗位链接、公司、薪资、地点。",
    ]
    return "\n".join(lines) + "\n"


def _relevant_projects(jd_text: str, facts: dict) -> list[dict]:
    """按 JD 文本与项目交付内容的关键词重合度挑选项目，只做重组不发明。"""
    projects = _as_list(facts.get("projects"))
    text = jd_text.lower()

    def overlap(p: dict) -> int:
        blob = " ".join(
            str(p.get(k) or "") for k in ("name", "background", "role")
        ) + " " + " ".join(str(x) for x in _as_list(p.get("delivered")))
        return sum(1 for w in text if w.isascii() and len(w) > 2 and w.lower() in blob.lower())

    scored = sorted(((overlap(p), p) for p in projects), key=lambda sp: sp[0], reverse=True)
    return [p for _, p in scored[:3]]


def render_resume_draft(res: dict, jd: dict, facts: dict) -> str:
    basics = facts.get("basics") or {}
    uni = _skill_universe(facts)
    jd_text = jd.get("jd_text") or ""
    text = jd_text.lower()

    hands_on = _as_list((facts.get("skills") or {}).get("expert")) + \
        _as_list((facts.get("skills") or {}).get("practiced"))
    matched = [s for s in hands_on if str(s).lower() in text]
    matched = list(dict.fromkeys(matched))  # 去重，保持顺序

    lines = [
        f"# 岗位版简历草稿（{jd.get('company', '')} · {jd.get('position', '')}）",
        "",
        f"> 生成规则：内容只重组自 candidate/private/facts.yml，无来源的一律标 [needs_proof]。",
        f"> 版本：v1-draft｜评估总分：{res['total']}（{res['verdict']}）｜生成日期：{res['evaluated_at']}",
        "",
        "## 基本信息",
        "",
        f"- 姓名：{basics.get('name') or '[needs_proof: 待填]'}",
        f"- 定位：{basics.get('title') or '[needs_proof: 待填]'}",
        f"- 年限：{basics.get('years_of_experience') or '[needs_proof: 待填]'}",
        f"- 学历：{basics.get('education') or '[needs_proof: 待填]'}",
        f"- 联系方式：[仅投递时填写，不留存于模板]",
        "",
        "## 技能（只列 JD 命中的实操技能）",
        "",
    ]
    if matched:
        lines += [f"- {s}（实操：expert/practiced，有交付或使用记录）" for s in matched]
    else:
        lines += ["- [needs_proof: JD 命中技能为空——检查 facts.yml 技能清单是否已填写]"]

    lines += ["", "## 项目经历（按与 JD 的相关度排序）", ""]
    projects = _relevant_projects(jd_text, facts)
    if not projects:
        lines += ["[needs_proof: 事实库没有项目记录——先补 candidate/private/projects.md]"]
    for p in projects:
        status = p.get("status") or "needs_proof"
        lines += [
            f"### {p.get('name') or '[待填项目名]'}"
            + ("  **[needs_proof]**" if status == "needs_proof" else ""),
            "",
            f"- 角色：{p.get('role') or '[待填：主导/参与/支持]'}｜"
            f"{p.get('start', '?')} ~ {p.get('end', '?')}",
            f"- 背景：{p.get('background') or '[待补一句话背景]'}",
            "- 交付：",
        ]
        for d in _as_list(p.get("delivered")) or ["[待补交付条目]"]:
            lines.append(f"  - {d}")
        metrics = _as_list(p.get("metrics"))
        if metrics:
            lines.append("- 结果（可核实）：")
            lines += [f"  - {m}" for m in metrics]
        lines.append("")

    gap = [s for s in uni["learned"] if s in text.lower()]
    lines += ["## 差距与如实口径", ""]
    if gap:
        lines += [
            f"- JD 提到但你仅学习过（不可写成经验）：{gap}",
            "- 如被问到，如实说明学习路径与练手范围，不声称交付经历",
        ]
    else:
        lines += ["- 未识别到 learned 技能被 JD 硬性要求"]
    lines += [
        "",
        "---",
        "本文件是重组草稿，不是可投递版本。人工核对每一行、补齐 needs_proof 后，",
        "另存为正式版本并登记 tracker 的 resume_version。",
    ]
    return "\n".join(lines) + "\n"


def render_outreach(res: dict, jd: dict) -> str:
    return "\n".join([
        f"# 开场文案（{jd.get('company', '')} · {jd.get('position', '')}）",
        "",
        "> 骨架由脚本生成，称呼、细节由人工补写；不要添加事实库之外的履历信息。",
        "",
        "## 站内信/好友申请（短）",
        "",
        "您好，看到贵司「" + (jd.get("position") or "[岗位名]") + "」岗位。",
        "我有「[一句话定位：从 facts.yml basics.title 复制]」的背景，",
        "在「[领域：从匹配项目的 background 各取一句]」有可核对的交付经历，期待进一步沟通。",
        "",
        "## 正文（长，按需用）",
        "",
        "- 开头：一句话说明从哪看到岗位、为什么是",
        "- 中段：2-3 条与 JD 对应的交付事实（从事实库复制，不扩写）",
        "- 结尾：可到岗时间 + 联系方式",
        "",
        "---",
        f"评估总分：{res['total']}（{res['verdict']}）｜生成日期：{res['evaluated_at']}",
    ]) + "\n"


def render_interview_prep(res: dict, jd: dict, facts: dict) -> str:
    projects = _relevant_projects(jd.get("jd_text") or "", facts)
    lines = [
        f"# 面试准备（{jd.get('company', '')} · {jd.get('position', '')}）",
        "",
        "## 必答题（每条都能答上证据链）",
        "",
        "1. 简历上每一条交付：背景 → 你做了什么 → 结果 → 证据在哪",
        "2. 离职原因（每段经历各一版，口径与事实库一致）",
        "3. 薪资期望与底线（口头报价与 facts.yml 一致）",
        "",
        "## 基于本项目 JD 的预测追问",
        "",
    ]
    senior = [w for w in ("主导", "架构", "带教") if w in (jd.get("jd_text") or "")]
    if senior:
        lines += [f"- JD 出现「{ '、'.join(senior) }」，预期会问主导经验：只讲 role=主导 的项目，参与项目如实说参与"]
    lines += [
        "- JD 中的每项硬性技能都可能被问深度：对照 facts.yml 的三档技能，learned 档准备「学习路径」话术而非「经验」话术",
        "",
        "## 证据索引（面试前过一遍）",
        "",
    ]
    for p in projects:
        lines.append(f"- {p.get('name', '[项目名]')}：{', '.join(_as_list(p.get('evidence'))) or '[待补证据]'}")
    lines += [
        "",
        "---",
        "答不上来的问题记入面试后复盘，回填事实库 needs_proof 清单。",
    ]
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------- 写盘

def update_tracker(workspace: Path, res: dict, jd: dict) -> str:
    path = workspace / "applications" / "private" / "tracker.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    rows: list[dict] = []
    if path.exists():
        with open(path, "r", encoding="utf-8", newline="") as fh:
            rows = [r for r in csv.DictReader(fh) if r.get("job_id")]
    sal = res.get("salary") or {}
    new_row = {
        "collected_date": jd.get("collected_at") or res["evaluated_at"],
        "job_id": res["job_id"],
        "company": res["company"],
        "position": res["position"],
        "city": res["city"],
        "salary_min_k": sal.get("min_k", ""),
        "salary_max_k": sal.get("max_k", ""),
        "score": res["total"],
        "verdict": res["verdict"],
        "status": "scored" if res["verdict"] != "eliminated" else "eliminated",
        "resume_version": "",
        "source_url": res["source_url"],
        "next_action": {
            "advance": "定制材料并尽快投递",
            "review": "人工复核后再决定",
            "watch": "观察，暂不投入",
            "pass": "放弃",
            "eliminated": "红线淘汰，不投",
        }[res["verdict"]],
        "notes": "; ".join(res["redline"]["reasons"] + res["redline"]["manual_review"])[:200],
    }
    replaced = False
    for i, r in enumerate(rows):
        if r.get("job_id") == res["job_id"]:
            # 人工字段不覆盖：已推进的 status、已定的 resume_version
            status = r.get("status") or ""
            if status in ("scored", "eliminated", ""):
                status = new_row["status"]
            rows[i] = {
                **new_row,
                "status": status,
                "resume_version": r.get("resume_version") or "",
            }
            replaced = True
            break
    if not replaced:
        rows.append(new_row)
    with open(path, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=TRACKER_HEADER)
        w.writeheader()
        w.writerows(rows)
    return "updated" if replaced else "appended"


def write_artifacts(workspace: Path, res: dict, jd: dict, facts: dict, dry: bool = False) -> dict:
    out = {"report_md": None, "report_json": None, "resume": None, "outreach": None,
           "interview": None, "tracker": None}
    if dry:
        return out
    reports = workspace / "reports" / "private"
    outputs = workspace / "outputs" / "private" / res["job_id"]
    reports.mkdir(parents=True, exist_ok=True)
    outputs.mkdir(parents=True, exist_ok=True)
    out["report_md"] = reports / f"{res['job_id']}.md"
    out["report_md"].write_text(render_report_md(res, jd), encoding="utf-8")
    out["report_json"] = reports / f"{res['job_id']}.json"
    out["report_json"].write_text(
        json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
    out["resume"] = outputs / "resume-draft.md"
    out["resume"].write_text(render_resume_draft(res, jd, facts), encoding="utf-8")
    out["outreach"] = outputs / "outreach.md"
    out["outreach"].write_text(render_outreach(res, jd), encoding="utf-8")
    out["interview"] = outputs / "interview-prep.md"
    out["interview"].write_text(render_interview_prep(res, jd, facts), encoding="utf-8")
    out["tracker"] = update_tracker(workspace, res, jd)
    return out


# ---------------------------------------------------------------- 入口

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="评估单个 JD 并产出全套材料草稿")
    ap.add_argument("--workspace", default=".", help="工作区根目录（默认当前目录）")
    ap.add_argument("--jd", required=True, help="JD JSON 文件路径")
    ap.add_argument("--today", default=None, help="覆盖评估日期 YYYY-MM-DD（测试用）")
    ap.add_argument("--dry-run", action="store_true", help="只评估打印，不写任何文件")
    args = ap.parse_args(argv)

    workspace = Path(args.workspace).resolve()
    rules_path = workspace / "config" / "scoring.yml"
    if not rules_path.exists():
        print(f"[error] 找不到评分规则：{rules_path}", file=sys.stderr)
        return 2
    jd_path = Path(args.jd)
    if not jd_path.exists():
        print(f"[error] 找不到 JD 文件：{jd_path}", file=sys.stderr)
        return 2

    rules = load_file(rules_path)
    facts = load_facts(workspace)
    if facts is None:
        print("[warn] candidate/private/facts.yml 不存在，事实库按空处理；"
              "先复制 candidate/templates/facts.yml 填写后重评更准")
    jd = load_json(jd_path)
    today = (
        datetime.strptime(args.today, "%Y-%m-%d").date()
        if args.today else date.today()
    )

    res = evaluate(jd, facts, rules, today)
    write_artifacts(workspace, res, jd, facts or {}, dry=args.dry_run)

    print(f"岗位：{res['company']} · {res['position']}")
    print(f"结论：总分 {res['total']} → {res['verdict']}"
          + ("（数据不全，仅供粗筛）" if res["data_incomplete"] else ""))
    if res["redline"]["reasons"]:
        for r in res["redline"]["reasons"]:
            print(f"  [红线] {r}")
    for d, v in res["dimensions"].items():
        print(f"  {d:<18} {v['score']:>3}  {v['note']}")
    if args.dry_run:
        print("(dry-run：未写任何文件)")
    else:
        print("产物：")
        print(f"  评估报告   reports/private/{res['job_id']}.md")
        print(f"  简历草稿   outputs/private/{res['job_id']}/resume-draft.md")
        print(f"  开场文案   outputs/private/{res['job_id']}/outreach.md")
        print(f"  面试准备   outputs/private/{res['job_id']}/interview-prep.md")
        print("  tracker    applications/private/tracker.csv 已更新")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
