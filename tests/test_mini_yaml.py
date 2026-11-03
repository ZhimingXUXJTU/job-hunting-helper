"""mini_yaml 的回归测试（虚构数据）。"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
from mini_yaml import YamlLiteError, parse  # noqa: E402


class TestScalars(unittest.TestCase):
    def test_scalar_types(self):
        doc = parse("\n".join([
            "empty:",
            "nul: null",
            "tilde: ~",
            "yes: true",
            "no: false",
            "int: 42",
            "neg: -7",
            "float: 3.14",
            "str: hello",
            "quoted: \"42\"",
        ]))
        self.assertIsNone(doc["empty"])
        self.assertIsNone(doc["nul"])
        self.assertIsNone(doc["tilde"])
        self.assertIs(doc["yes"], True)
        self.assertIs(doc["no"], False)
        self.assertEqual(doc["int"], 42)
        self.assertEqual(doc["neg"], -7)
        self.assertEqual(doc["float"], 3.14)
        self.assertEqual(doc["str"], "hello")
        self.assertEqual(doc["quoted"], "42")

    def test_inline_list(self):
        doc = parse("cities: [上海, 杭州]\nempty: []\nsingle: [x]")
        self.assertEqual(doc["cities"], ["上海", "杭州"])
        self.assertEqual(doc["empty"], [])
        self.assertEqual(doc["single"], ["x"])

    def test_comment_and_blank(self):
        doc = parse("# 顶部注释\n\nkey: value  # 行尾注释\nurl: \"http://x/#/y\"")
        self.assertEqual(doc["key"], "value")
        # 引号内的 # 不当注释剥
        self.assertEqual(doc["url"], "http://x/#/y")

    def test_bad_indent(self):
        with self.assertRaises(YamlLiteError):
            parse("a:\n   b: 1")


class TestNested(unittest.TestCase):
    def test_nested_map(self):
        text = "\n".join([
            "basics:",
            "  name: n",
            "  nested:",
            "    deep: 1",
            "top: true",
        ])
        doc = parse(text)
        self.assertEqual(doc["basics"]["name"], "n")
        self.assertEqual(doc["basics"]["nested"]["deep"], 1)
        self.assertIs(doc["top"], True)

    def test_scalar_list(self):
        text = "\n".join([
            "skills:",
            "  learned:",
            "    - RAG",
            "    - Kubernetes",
        ])
        doc = parse(text)
        self.assertEqual(doc["skills"]["learned"], ["RAG", "Kubernetes"])

    def test_map_list(self):
        text = "\n".join([
            "projects:",
            "  - name: one",
            "    role: 参与",
            "    status: verified",
            "  - name: two",
            "    role: 主导",
            "    status: needs_proof",
        ])
        doc = parse(text)
        items = doc["projects"]
        self.assertEqual(len(items), 2)
        self.assertEqual(items[0], {"name": "one", "role": "参与", "status": "verified"})
        self.assertEqual(items[1]["name"], "two")
        self.assertEqual(items[1]["status"], "needs_proof")

    def test_real_fixture(self):
        fixture = Path(__file__).parent / "fixtures" / "fake_facts.yml"
        facts = parse(fixture.read_text(encoding="utf-8"))
        self.assertEqual(facts["basics"]["years_of_experience"], 5)
        self.assertEqual(facts["preferences"]["cities"], ["上海"])
        self.assertEqual(len(facts["projects"]), 3)
        self.assertEqual(facts["projects"][1]["role"], "主导")
        self.assertEqual(facts["skills"]["learned"], ["RAG", "Kubernetes"])


if __name__ == "__main__":
    unittest.main()
