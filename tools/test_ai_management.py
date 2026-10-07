"""工作管理工具的離線回歸測試與假 CLI 背景派工驗證。"""
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import office_common as common
import codex_rpc
import registry


def load(name):
    spec = importlib.util.spec_from_file_location(name.replace("-", "_"), HERE / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


run = load("codex-run")
status = load("dispatch-status")
audit = load("doc-audit")
update = load("codex-autoupdate")
fetch = load("official-docs-fetch")
quota = load("codex-quota")
claude = load("claude-quota")
queue_tool = load("codex-queue")

KNOWLEDGE = """---
name: codex-models
description: 模型與額度
type: reference
status: current
updated: 2026-01-01
---
# 模型
保留人工建議。
<!-- CODEX-MODELS:BEGIN -->
舊資料
<!-- CODEX-MODELS:END -->
末段保留。
"""
ROWS = [{"slug": "example-model", "description": "Coding | general", "default": "low", "efforts": ["low", "high"]}]


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        env = mock.patch.dict(os.environ, {"AI_OFFICE_STATE": str(self.root / "state")})
        env.start()
        self.addCleanup(env.stop)

    def write(self, relative, text="x"):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path


class CommonTests(Base):
    def test_atomic_unicode_json(self):
        path = self.root / "中文 空白" / "data.json"
        common.write_json(path, {"title": "交辦"})
        self.assertEqual(common.read_json(path), {"title": "交辦"})
        self.assertEqual(len(list(path.parent.glob("*.tmp"))), 0)

    def test_memory_units_and_invalid(self):
        self.assertEqual(common.memory_bytes("1.5G"), int(1.5 * 1024**3))
        for value in ("0", "-2G", "infinity", "20%", "bad"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                common.memory_bytes(value)

    def test_lock_is_exclusive_and_releases(self):
        with common.runtime_lock():
            with self.assertRaises(RuntimeError):
                with common.runtime_lock():
                    pass
        self.assertFalse((common.state_dir() / "runtime.lock").exists())

    def test_live_and_dead_pid(self):
        self.assertTrue(common.alive(os.getpid()))
        self.assertFalse(common.alive(-1))
        self.assertFalse(common.alive(None))

    def test_windows_cmd_uses_node_without_shell(self):
        wrapper = self.write("npm/codex.cmd", "@echo off")
        entry = self.write("npm/node_modules/@openai/codex/bin/codex.js", "// entry")
        with mock.patch.object(common.os, "name", "nt"), mock.patch.object(common.shutil, "which", side_effect=[str(wrapper), "node.exe"]):
            # pathlib 在非 Windows 主機仍使用實際 Path 類別。
            with mock.patch.object(common, "Path", type(self.root)):
                self.assertEqual(common.cli("codex"), ["node.exe", str(entry)])


class RegistryAuditTests(Base):
    def test_registry_uses_docstrings_skips_tests_and_checks(self):
        self.write("tools/a.py", '"""工具用途。\n用法：python a.py\n"""\n')
        self.write("tools/test_a.py", "# test only")
        target, text, errors = registry.generate("tools", self.root / "tools")
        self.assertFalse(errors)
        self.assertIn("[a.py](a.py)", text)
        self.assertNotIn("test_a.py", text)
        self.assertEqual(registry.main(["tools", str(target.parent)]), 0)
        self.assertEqual(registry.main(["tools", str(target.parent), "--check"]), 0)
        self.write("tools/a.py", '"""新用途。\n用法：python a.py\n"""\n')
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(registry.main(["tools", str(target.parent), "--check"]), 1)

    def test_knowledge_metadata_missing(self):
        self.write("knowledge/a.md", "# missing metadata")
        _, _, errors = registry.generate("knowledge", self.root / "knowledge")
        self.assertTrue(errors)

    def test_mtime_handoff_and_registry(self):
        handoff = self.write("docs/HANDOFF.md", "# 交接")
        tool = self.write("tools/a.py", '"""用途。\n用法：a.py\n"""')
        registry.main(["tools", str(tool.parent)])
        os.utime(handoff, (10, 10))
        os.utime(tool.parent / "REGISTRY.md", (20, 20))
        os.utime(tool, (30, 30))
        findings = audit.audit(self.root)
        self.assertTrue(any("HANDOFF" in f for f in findings))
        self.assertTrue(any("比來源" in f for f in findings))

    def test_local_link_checks_urls_anchors_fences_and_unicode(self):
        self.write("exists 中文.md")
        self.write("README.md", "[ok](exists%20%E4%B8%AD%E6%96%87.md#heading)\n[web](https://example.com)\n[anchor](#id)\n[bad](missing.md)\n```md\n[example](example.md)\n```\n[ref]: other.md\n")
        findings = audit.audit(self.root)
        self.assertEqual(len(findings), 2)
        self.assertTrue(any("missing.md" in f for f in findings))
        self.assertTrue(any("other.md" in f for f in findings))

    def test_excludes_inbox_and_scratch(self):
        self.write("scratch/README.md", "[bad](absent.md)")
        self.write("inbox/README.md", "[bad](absent.md)")
        self.assertEqual(audit.audit(self.root), [])

    def test_git_is_optional(self):
        self.write("README.md")
        with mock.patch.object(audit.subprocess, "run") as call:
            self.assertEqual(audit.audit(self.root), [])
            call.assert_not_called()
        (self.root / ".git").mkdir()
        with mock.patch.object(audit.shutil, "which", return_value="git"), mock.patch.object(audit.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, "changed\n", "")):
            self.assertEqual(len(audit.audit(self.root, include_git=True)), 2)


class ModelUpdateTests(Base):
    def test_cache_fields_hidden_filtered(self):
        data = {"identity": "private", "models": [
            {"slug": "visible", "visibility": "list", "default_reasoning_level": "low", "supported_reasoning_levels": [{"effort": "high"}]},
            {"slug": "hidden", "visibility": "hide"}]}
        rows = update.normalize_cache(data)
        self.assertEqual([r["slug"] for r in rows], ["visible"])
        self.assertNotIn("identity", str(rows))

    def test_update_preserves_prose_and_rebuilds_index(self):
        path = self.write("knowledge/codex-models.md", KNOWLEDGE)
        update.update_knowledge(path, ROWS, "test source", "2026-10-07", "1.0.0")
        text = path.read_text(encoding="utf-8")
        self.assertIn("保留人工建議", text)
        self.assertIn("末段保留", text)
        self.assertIn("updated: 2026-10-07", text)
        self.assertIn("Coding \\| general", text)
        self.assertTrue((path.parent / "INDEX.md").is_file())

    def test_empty_catalog_does_not_replace(self):
        with self.assertRaises(ValueError):
            update.validate_models([])
        with self.assertRaises(ValueError):
            update.validate_models(ROWS * 2)

    def test_no_markers_refuses_write(self):
        path = self.write("knowledge/codex-models.md", "# existing")
        with self.assertRaises(ValueError):
            update.update_knowledge(path, ROWS, "test", "2026-10-07", "1.0.0")
        self.assertEqual(path.read_text(), "# existing")

    def test_invalid_index_metadata_does_not_partially_update(self):
        path = self.write("knowledge/codex-models.md", KNOWLEDGE)
        self.write("knowledge/other.md", "# missing metadata")
        with self.assertRaises(ValueError):
            update.update_knowledge(path, ROWS, "test", "2026-10-07", "1.0.0")
        self.assertEqual(path.read_text(), KNOWLEDGE)

    def test_offline_refresh_notification_then_idempotent(self):
        path = self.write("knowledge/codex-models.md", KNOWLEDGE)
        cache = self.write("cache.json", json.dumps({"fetched_at": "2026-09-01T00:00:00Z", "client_version": "1.0.0", "models": [{
            "slug": "new-model", "visibility": "list", "description": "new", "supported_reasoning_levels": []}]}))
        args = ["--refresh-only", "--cache", str(cache), "--knowledge", str(path)]
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(update.main(args), 0)
            self.assertEqual(update.main(args), 0)
        self.assertIn("資料日期：2026-09-01", path.read_text())
        self.assertEqual(len(list((common.state_dir() / "inbox").glob("*.md"))), 1)

    def test_dry_run_has_no_state_or_knowledge_writes(self):
        path = self.write("knowledge/codex-models.md", KNOWLEDGE)
        cache = self.write("cache.json", json.dumps({"fetched_at": "2026-10-07", "models": [{"slug": "a", "visibility": "list"}]}))
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(update.main(["--dry-run", "--refresh-only", "--cache", str(cache), "--knowledge", str(path)]), 0)
        self.assertEqual(path.read_text(), KNOWLEDGE)
        self.assertFalse(common.state_dir().exists())

    def test_successful_upgrade_has_smoke(self):
        with mock.patch.object(update, "npm_install", return_value=subprocess.CompletedProcess([], 0)), mock.patch.object(update, "installed_version", return_value="2.0.0"), mock.patch.object(update, "smoke", return_value=True) as smoke:
            result = update.upgrade("1.0.0", "2.0.0", None, None)
        self.assertTrue(result["ok"])
        smoke.assert_called_once()

    def test_failed_smoke_rolls_back_and_verifies(self):
        with mock.patch.object(update, "npm_install", return_value=subprocess.CompletedProcess([], 0)) as install, mock.patch.object(update, "installed_version", side_effect=["2.0.0", "1.0.0"]), mock.patch.object(update, "smoke", return_value=False):
            result = update.upgrade("1.0.0", "2.0.0", None, None)
        self.assertFalse(result["ok"])
        self.assertEqual(result["rollback"], "verified")
        self.assertEqual([call.args[0] for call in install.call_args_list], ["2.0.0", "1.0.0"])

    def test_rollback_failure_is_not_success(self):
        with mock.patch.object(update, "npm_install", return_value=subprocess.CompletedProcess([], 1)), mock.patch.object(update, "installed_version", return_value="2.0.0"):
            result = update.upgrade("1.0.0", "2.0.0", None, None)
        self.assertEqual(result["rollback"], "failed-or-unknown")

    def test_unknown_upgrade_timeout_does_not_reinstall(self):
        with mock.patch.object(update, "npm_install", side_effect=subprocess.TimeoutExpired("npm", 10)) as install:
            result = update.upgrade("1.0.0", "2.0.0", None, None)
        self.assertEqual(result["rollback"], "not-run")
        self.assertEqual(install.call_count, 1)


class FetchTests(Base):
    def test_index_filter_and_filenames(self):
        text = "https://code.claude.com/docs/en/a.md https://evil.example/a.md https://code.claude.com/docs/zh-TW/a.md"
        self.assertEqual(fetch.page_urls(text, "code.claude.com", r"/en/"), ["https://code.claude.com/docs/en/a.md"])
        self.assertNotEqual(fetch.filename("https://example.com/a/x.md"), fetch.filename("https://example.com/b/x.md"))

    def test_success_and_failed_refresh_preserves_page(self):
        dest = self.root / "docs"
        url = "https://code.claude.com/docs/en/test.md"
        with mock.patch.object(fetch, "get", side_effect=[url, "# Good\n內容"]):
            self.assertTrue(fetch.fetch_site("claude-code", dest, 1)["ok"])
        page = dest / fetch.filename(url)
        before = page.read_bytes()
        with mock.patch.object(fetch, "get", side_effect=[url, OSError("network error")]):
            self.assertFalse(fetch.fetch_site("claude-code", dest, 1)["ok"])
        self.assertEqual(page.read_bytes(), before)
        row = common.read_json(dest / "manifest.json")["pages"][0]
        self.assertEqual(row["status"], "failed")
        self.assertTrue(row.get("fetched_at"))

    def test_empty_index_is_failure(self):
        with mock.patch.object(fetch, "get", return_value="nothing"):
            self.assertFalse(fetch.fetch_site("claude-code", self.root / "docs", 1)["ok"])

    def test_removed_pages_remain_marked(self):
        url = "https://code.claude.com/docs/en/new.md"
        dest = self.root / "docs"
        common.write_json(dest / "manifest.json", {"pages": [{"url": "old", "file": "old.md", "status": "ok"}]})
        with mock.patch.object(fetch, "get", side_effect=[url, "# New"]):
            fetch.fetch_site("claude-code", dest, 1)
        self.assertEqual(common.read_json(dest / "manifest.json")["pages"][1]["status"], "removed-from-index")

    def test_claude_combined_text_fallback(self):
        url = "https://code.claude.com/docs/en/test.md"
        combined = "# Test\nSource: https://code.claude.com/docs/en/test\n\n官方內文\n\n# Other\nSource: https://code.claude.com/docs/en/other\n其他內容"
        dest = self.root / "docs"
        with mock.patch.object(fetch, "get", side_effect=[url, ValueError("redirected to HTML"), combined]):
            result = fetch.fetch_site("claude-code", dest, 1)
        self.assertTrue(result["ok"])
        row = common.read_json(dest / "manifest.json")["pages"][0]
        self.assertEqual(row["fetched_from"], "https://code.claude.com/docs/llms-full.txt")
        self.assertIn("官方內文", (dest / row["file"]).read_text())
        self.assertNotIn("其他內容", (dest / row["file"]).read_text())

    def test_nonofficial_urls_rejected(self):
        with self.assertRaises(ValueError):
            fetch.get("https://example.com/test.md")


class QuotaTests(Base):
    def test_missing_windows_is_unknown(self):
        self.assertEqual(list(quota.windows({"rateLimits": None})), [])
        with mock.patch.object(quota, "AppServer") as app, contextlib.redirect_stdout(io.StringIO()) as out:
            app.return_value.__enter__.return_value.request.return_value = {"rateLimits": None}
            self.assertEqual(quota.main(["--json"]), 0)
        info = json.loads(out.getvalue())
        self.assertFalse(info["available"])

    def test_null_secondary_and_multiple_buckets(self):
        data = {"rateLimitsByLimitId": {"one": {"primary": {"usedPercent": 5}, "secondary": None}, "two": {"secondary": {"usedPercent": 0}}}}
        self.assertEqual(len(list(quota.windows(data))), 2)

    def test_claude_has_no_fake_remaining_or_network_calls(self):
        with contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(claude.main(["--json"]), 0)
        info = json.loads(out.getvalue())
        self.assertIsNone(info["remaining"])
        self.assertFalse(info["available"])

    def test_rpc_timeout_does_not_block_on_readline(self):
        fake = self.write("silent.py", "import time\ntime.sleep(5)\n")
        start = time.monotonic()
        with mock.patch.object(codex_rpc, "cli", return_value=[sys.executable, str(fake)]):
            with self.assertRaises(TimeoutError):
                with codex_rpc.AppServer(timeout=0.05):
                    pass
        self.assertLess(time.monotonic() - start, 2)


class DispatchTests(Base):
    def test_interrupted_and_missing_report(self):
        job = self.root / "job"
        common.write_json(job / "job.json", {"pid": -1, "status": "running"})
        self.assertEqual(run.job_status(job)["status"], "interrupted")
        common.write_json(job / "summary.json", {"ok": True})
        self.assertEqual(run.job_status(job)["status"], "missing-report")
        common.write_text(job / "result.md", "report")
        self.assertEqual(run.job_status(job)["status"], "done")

    def test_status_overview_skips_scratch(self):
        common.write_json(self.root / "one" / "job.json", {"pid": -1})
        common.write_json(self.root / "one" / "scratch" / "job.json", {"pid": -1})
        self.assertEqual(len(status.jobs(self.root)), 1)

    def test_resource_queue_times_out_before_submit(self):
        with mock.patch.object(queue_tool, "available_memory", return_value=0), mock.patch.object(queue_tool.subprocess, "run") as call, contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(queue_tool.main(["--min-free", "1G", "--max-wait", "0", "--brief", "x", "--out", "y"]), 2)
            call.assert_not_called()

    def test_worker_utf8_and_error_summary_with_real_fake_process(self):
        fake = self.write("fake.py", """import json, pathlib, sys
prompt=sys.stdin.read()
pathlib.Path(sys.argv[sys.argv.index('-o')+1]).write_text('完成：'+prompt,encoding='utf-8')
print(json.dumps({'type':'thread.started','thread_id':'test-thread'}))
print(json.dumps({'type':'turn.completed','usage':{'input_tokens':12,'output_tokens':3}}))
""")
        out = self.root / "工作 空白"
        out.mkdir()
        common.write_text(out / "brief.md", "請處理中文")
        common.write_json(out / "job.json", {"job_id": "test", "params": {"cwd": str(self.root), "model": "example", "effort": "high", "search": False, "sandbox": "workspace-write", "codex_home": None, "memory_max": None}})
        with mock.patch.object(run, "cli", return_value=[sys.executable, str(fake)]):
            self.assertEqual(run.worker(out), 0)
        info = common.read_json(out / "summary.json")
        self.assertEqual(info["thread_id"], "test-thread")
        self.assertEqual(info["usage"], {"input_tokens": 12, "output_tokens": 3})
        self.assertIn("請處理中文", (out / "result.md").read_text())
        with mock.patch.object(run, "cli", side_effect=FileNotFoundError("no CLI")):
            self.assertEqual(run.worker(out), 1)
        self.assertFalse(common.read_json(out / "summary.json")["ok"])

    @unittest.skipIf(os.name == "nt", "假 shebang CLI 僅用於 Linux 背景整合；Windows 分離行程待實機驗證")
    def test_submit_wait_and_duplicate_output_with_detached_worker(self):
        fake = self.write("bin/codex", "#!" + sys.executable + "\n" + """import json,pathlib,sys,time
prompt=sys.stdin.read()
time.sleep(0.4)
pathlib.Path(sys.argv[sys.argv.index('-o')+1]).write_text('測試成功',encoding='utf-8')
print(json.dumps({'type':'thread.started','thread_id':'detached-test'}))
print(json.dumps({'type':'turn.completed','usage':{'input_tokens':1}}))
""")
        fake.chmod(0o755)
        brief = self.write("中文 brief.md", "請回覆測試成功")
        out = self.root / "inbox" / "codex" / "task"
        env = dict(os.environ, PATH=str(fake.parent) + os.pathsep + os.environ["PATH"])
        command = [sys.executable, str(HERE / "codex-run.py")]
        sent = subprocess.run(command + ["submit", "--brief", str(brief), "--out", str(out), "--cwd", str(self.root)], env=env, capture_output=True, text=True, timeout=10)
        self.assertEqual(sent.returncode, 0, sent.stdout + sent.stderr)
        self.assertTrue(json.loads(sent.stdout)["ok"])
        timed = subprocess.run(command + ["wait", str(out), "--timeout", "0"], env=env, capture_output=True, text=True, timeout=10)
        self.assertIn(timed.returncode, (0, 2))
        done = subprocess.run(command + ["wait", str(out), "--timeout", "1"], env=env, capture_output=True, text=True, timeout=10)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertTrue(json.loads(done.stdout)["ok"])
        again = subprocess.run(command + ["submit", "--brief", str(brief), "--out", str(out)], env=env, capture_output=True, text=True, timeout=10)
        self.assertEqual(again.returncode, 1)
        self.assertEqual((out / "result.md").read_text(encoding="utf-8"), "測試成功")


if __name__ == "__main__":
    unittest.main()
