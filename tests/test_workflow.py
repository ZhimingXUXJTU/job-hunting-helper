"""run_workflow 评估闭环的回归测试（全部使用虚构数据，不碰真实记录）。"""

from __future__ import annotations

import csv
import json
import shutil
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
from mini_yaml import load_file  # noqa: E402
from run_workflow import evaluate, main, render_resume_draft, update_tracker  # noqa: E402

FIX = ROOT / "tests" / "fixtures"
TODAY = date(2026, 4, 1)


def _load_rules() -> dict:
    return load_file(ROOT / "config" / "scoring.yml")


def _load_facts() -> dict:
    return load_file(FIX / "fake_facts.yml")


def _jd(name: str) -> dict:
    return json.loads((FIX / name).read_text(encoding="utf-8"))


class TestRedlines(unittest.TestCase):
    def test_outsource_eliminated(self):
        res = evaluate(_jd("jd_outsource.json"), _load_facts(), _load_rules(), TODAY)
        self.assertTrue(res["redline"]["eliminated"])
        self.assertEqual(res["verdict"], "eliminated")
        self.assertEqual(res["total"], 0)
        self.assertTrue(any("外包" in r for r in res["redline"]["reasons"]))

    def test_low_salary_not_eliminated(self):
        """薪资不是红线：低薪岗位不淘汰，只在 salary 维度减分。"""
        res = evaluate(_jd("jd_lowsalary.json"), _load_facts(), _load_rules(), TODAY)
        self.assertFalse(res["redline"]["eliminated"])
        self.assertEqual(res["dimensions"]["salary"]["score"], 30)
        self.assertTrue(any("不构成一票否决" in n for n in res["notes"]))

    def test_salary_floor_only_affects_score(self):
        """底线与期望都高于 JD 上限时不再淘汰，薪资维度落到最低档。"""
        facts = _load_facts()
        facts["preferences"]["salary_floor_k"] = 36   # 高于 JD 上限 35k
        facts["preferences"]["salary_expect_k"] = 40
        res = evaluate(_jd("jd_normal.json"), facts, _load_rules(), TODAY)
        self.assertFalse(res["redline"]["eliminated"])
        self.assertEqual(res["dimensions"]["salary"]["score"], 30)
        self.assertTrue(any("只减分" in n for n in res["notes"]))


class TestScoring(unittest.TestCase):
    def test_normal_jd_scores(self):
        res = evaluate(_jd("jd_normal.json"), _load_facts(), _load_rules(), TODAY)
        self.assertFalse(res["redline"]["eliminated"])
        dims = res["dimensions"]
        # 技能证据：JD 提到 python/fastapi/mysql/redis/docker 全部 expert/practiced → 满分
        self.assertEqual(dims["skill_evidence"]["score"], 100)
        # 年限：要求 5 年，事实库 5 年 → 90
        self.assertEqual(dims["responsibility"]["score"], 90)
        # 方向：JD 命中「交易系统」「支付」两词（「后端架构」未出现）→ 50 + 2/3*50 ≈ 83
        self.assertEqual(dims["direction"]["score"], 83)
        # 薪资：min 22k >= expect 25k? no; max 35 >= 25 → 90
        self.assertEqual(dims["salary"]["score"], 90)
        # 通勤：上海 ∈ 目标城市 → 90
        self.assertEqual(dims["commute"]["score"], 90)
        # 新鲜度：2026-03-30 距 4-1 两天 → 100
        self.assertEqual(dims["freshness"]["score"], 100)
        self.assertGreaterEqual(res["total"], 80)

    def test_missing_salary_marks_manual_review(self):
        jd = _jd("jd_normal.json")
        jd["salary"] = {}
        res = evaluate(jd, _load_facts(), _load_rules(), TODAY)
        self.assertTrue(any("未写薪资" in n for n in res["notes"]))
        self.assertTrue(res["data_incomplete"])

    def test_learned_never_counts_as_deliverable(self):
        jd = _jd("jd_normal.json")
        jd["jd_text"] = "要求精通 Kubernetes 与 RAG，5 年 Python 经验。"
        res = evaluate(jd, _load_facts(), _load_rules(), TODAY)
        note = " ".join(res["notes"])
        self.assertIn("learned", note)
        # required = {kubernetes, rag, python}，deliverable 只含 python → 1/3
        self.assertEqual(res["dimensions"]["skill_evidence"]["score"], 33)

    def test_thresholds(self):
        rules = _load_rules()
        adv = rules["thresholds"]["advance"]
        rev = rules["thresholds"]["review"]
        self.assertGreater(adv, rev)


class TestArtifacts(unittest.TestCase):
    def test_resume_draft_respects_facts(self):
        facts = _load_facts()
        res = evaluate(_jd("jd_normal.json"), facts, _load_rules(), TODAY)
        draft = render_resume_draft(res, _jd("jd_normal.json"), facts)
        # verified 项目（对账平台=主导）进入草稿
        self.assertIn("支付对账平台", draft)
        self.assertIn("主导", draft)
        # needs_proof 项目整体带标记，不冒充正式内容
        self.assertIn("[needs_proof]", draft)
        # learned 技能出现在「差距」区，不进技能清单的「实操」行
        self.assertIn("RAG", draft)
        self.assertNotIn("RAG（实操", draft)
        # 数字原样搬运
        self.assertIn("210ms", draft)
        self.assertNotIn("200ms", draft)

    def test_write_and_tracker_idempotent(self):
        workspace = Path(tempfile.mkdtemp(prefix="jh-test-"))
        try:
            (workspace / "config").mkdir()
            shutil.copy(ROOT / "config" / "scoring.yml", workspace / "config" / "scoring.yml")
            facts = _load_facts()
            jd = _jd("jd_normal.json")
            res = evaluate(jd, facts, _load_rules(), TODAY)

            from run_workflow import write_artifacts
            write_artifacts(workspace, res, jd, facts)
            tracker_path = workspace / "applications" / "private" / "tracker.csv"
            self.assertTrue(tracker_path.exists())
            with open(tracker_path, "r", encoding="utf-8", newline="") as fh:
                rows = list(csv.DictReader(fh))
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["job_id"], "fake-normal-20260401")
            self.assertEqual(rows[0]["status"], "scored")

            # 人工推进状态后重评，不覆盖人工字段、不重复行
            rows[0]["status"] = "applied"
            rows[0]["resume_version"] = "v2"
            with open(tracker_path, "w", encoding="utf-8", newline="") as fh:
                w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
                w.writeheader()
                w.writerows(rows)

            update_tracker(workspace, res, jd)
            with open(tracker_path, "r", encoding="utf-8", newline="") as fh:
                rows2 = list(csv.DictReader(fh))
            self.assertEqual(len(rows2), 1)
            self.assertEqual(rows2[0]["status"], "applied")
            self.assertEqual(rows2[0]["resume_version"], "v2")
        finally:
            shutil.rmtree(workspace, ignore_errors=True)

    def test_cli_dry_run_writes_nothing(self):
        workspace = Path(tempfile.mkdtemp(prefix="jh-test-"))
        try:
            (workspace / "config").mkdir()
            shutil.copy(ROOT / "config" / "scoring.yml", workspace / "config" / "scoring.yml")
            rc = main([
                "--workspace", str(workspace),
                "--jd", str(FIX / "jd_normal.json"),
                "--today", "2026-04-01",
                "--dry-run",
            ])
            self.assertEqual(rc, 0)
            self.assertFalse((workspace / "reports").exists())
            self.assertFalse((workspace / "outputs").exists())
        finally:
            shutil.rmtree(workspace, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
