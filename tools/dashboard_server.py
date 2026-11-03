#!/usr/bin/env python3
"""本地工作台服务器（零依赖，Python 3.10+）。

用法（在工作区根目录）：
    python -X utf8 tools/dashboard_server.py            # http://127.0.0.1:8765
    python -X utf8 tools/dashboard_server.py --port 9000

只读本地文件并输出一个统一快照 JSON；页面不调用云模型，不访问招聘平台，
数据只走本机回环地址。每次任务先读这个快照，结果保存后再回来登记。
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import date
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent))
from mini_yaml import load_file  # noqa: E402

DASHBOARD_DIR = Path(__file__).resolve().parent.parent / "dashboard"


def _read_text(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return None


def _load_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def build_snapshot(workspace: Path) -> dict:
    snap = {"generated_at": date.today().isoformat(), "workspace": str(workspace)}

    # ---- 候选人事实库摘要
    facts_path = workspace / "candidate" / "private" / "facts.yml"
    facts = load_file(facts_path) if facts_path.exists() else None
    if facts:
        skills = facts.get("skills") or {}
        projects = facts.get("projects") or []
        if not isinstance(projects, list):
            projects = []
        snap["candidate"] = {
            "ready": True,
            "title": (facts.get("basics") or {}).get("title") or "",
            "years": (facts.get("basics") or {}).get("years_of_experience"),
            "cities": (facts.get("preferences") or {}).get("cities") or [],
            "skills_count": {
                "expert": len(skills.get("expert") or []),
                "practiced": len(skills.get("practiced") or []),
                "learned": len(skills.get("learned") or []),
            },
            "projects_total": len(projects),
            "needs_proof": sum(
                1 for p in projects if isinstance(p, dict) and p.get("status") == "needs_proof"
            ),
        }
    else:
        snap["candidate"] = {
            "ready": False,
            "hint": "candidate/private/facts.yml 不存在：复制 candidate/templates/facts.yml 填写",
        }

    # ---- 待评估 JD（inbox）
    inbox = []
    inbox_dir = workspace / "jobs" / "inbox"
    if inbox_dir.is_dir():
        for p in sorted(inbox_dir.glob("*.json")):
            jd = _load_json(p)
            if isinstance(jd, dict):
                inbox.append({
                    "file": p.name,
                    "id": jd.get("id") or p.stem,
                    "company": jd.get("company") or "",
                    "position": jd.get("position") or "",
                    "collected_at": jd.get("collected_at") or "",
                })
    snap["inbox"] = inbox

    # ---- 评估结果
    evals = []
    reports_dir = workspace / "reports" / "private"
    if reports_dir.is_dir():
        for p in sorted(reports_dir.glob("*.json")):
            res = _load_json(p)
            if isinstance(res, dict) and res.get("job_id"):
                evals.append({
                    "job_id": res.get("job_id"),
                    "company": res.get("company"),
                    "position": res.get("position"),
                    "total": res.get("total"),
                    "verdict": res.get("verdict"),
                    "evaluated_at": res.get("evaluated_at"),
                    "data_incomplete": res.get("data_incomplete"),
                })
    snap["evals"] = list(reversed(evals))

    # ---- tracker
    tracker_rows = []
    tracker_path = workspace / "applications" / "private" / "tracker.csv"
    if tracker_path.exists():
        with open(tracker_path, "r", encoding="utf-8", newline="") as fh:
            tracker_rows = [r for r in csv.DictReader(fh) if r.get("job_id")]
    snap["tracker"] = list(reversed(tracker_rows))

    # ---- 产物清单
    outputs = []
    out_dir = workspace / "outputs" / "private"
    if out_dir.is_dir():
        for job_dir in sorted(p for p in out_dir.iterdir() if p.is_dir()):
            files = sorted(f.name for f in job_dir.iterdir() if f.is_file())
            if files:
                outputs.append({"job_id": job_dir.name, "files": files})
    snap["outputs"] = outputs

    # ---- 规则摘要
    rules_path = workspace / "config" / "scoring.yml"
    snap["rules"] = load_file(rules_path) if rules_path.exists() else None
    return snap


class Handler(BaseHTTPRequestHandler):
    workspace = Path.cwd()

    def log_message(self, fmt, *args):  # 安静模式，避免刷屏
        pass

    def _send(self, code: int, body: bytes, ctype: str):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/api/snapshot":
            body = json.dumps(
                build_snapshot(self.workspace), ensure_ascii=False, indent=2
            ).encode("utf-8")
            self._send(200, body, "application/json; charset=utf-8")
            return
        if path in ("/", "/index.html"):
            data = _read_text(DASHBOARD_DIR / "index.html")
            if data:
                self._send(200, data.encode("utf-8"), "text/html; charset=utf-8")
                return
        for name, ctype in (("app.js", "text/javascript; charset=utf-8"),
                            ("style.css", "text/css; charset=utf-8")):
            if path == f"/{name}":
                data = _read_text(DASHBOARD_DIR / name)
                if data:
                    self._send(200, data.encode("utf-8"), ctype)
                    return
        self._send(404, b"not found", "text/plain; charset=utf-8")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="本地求职工作台")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--workspace", default=".", help="工作区根目录（默认当前目录）")
    args = ap.parse_args(argv)
    Handler.workspace = Path(args.workspace).resolve()
    url = f"http://127.0.0.1:{args.port}"
    print(f"工作台：{url}（Ctrl+C 退出）")
    print(f"工作区：{Handler.workspace}")
    ThreadingHTTPServer(("127.0.0.1", args.port), Handler).serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
