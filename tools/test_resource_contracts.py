"""文件更新制度、兩端專案入口及已查證來源網址的回歸測試。"""
from pathlib import Path
import shutil
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent.parent


class ResourceContractTests(unittest.TestCase):
    def test_f5_existing_document_rule_has_project_exception(self):
        text = (ROOT / "templates/CLAUDE.md").read_text(encoding="utf-8")
        rule = next(line for line in text.splitlines() if "**修改檔案**" in line)
        self.assertIn("受版本控制", rule)
        self.assertIn("專案文件制度", rule)
        self.assertIn("其餘", rule)
        self.assertIn("另存", rule)
        self.assertIn("覆寫", rule)
        for relative in ("templates/AGENTS.md", "skills/handoff-docs/SKILL.md", "skills/project-docs/SKILL.md"):
            with self.subTest(file=relative):
                lines = (ROOT / relative).read_text(encoding="utf-8").splitlines()
                scoped = next(line for line in lines if "受版本控制" in line)
                self.assertIn("制度", scoped)
                self.assertIn("原路徑", scoped)
                self.assertIn("其餘", scoped)
                self.assertIn("另存", scoped)

    def test_f6_new_project_has_shared_native_entries(self):
        templates = ROOT / "skills/project-docs/templates"
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for name in ("CLAUDE.md", "AGENTS.md"):
                shutil.copyfile(templates / name, root / name)
            self.assertIn("@AGENTS.md", (root / "CLAUDE.md").read_text(encoding="utf-8"))
            self.assertIn("HANDOFF.md", (root / "AGENTS.md").read_text(encoding="utf-8"))
        skill = (ROOT / "skills/project-docs/SKILL.md").read_text(encoding="utf-8")
        self.assertIn('"$skill\\AGENTS.md"', skill)
        self.assertIn('"$skill\\CLAUDE.md"', skill)

    def test_f7_citations_use_verified_current_pages(self):
        replacements = {
            "knowledge/codex-models.md": "https://learn.chatgpt.com/docs/config-file/config-advanced",
            "tools/README-ai-management.md": "https://learn.chatgpt.com/docs/non-interactive-mode",
            "skills/codex-dispatch/SKILL.md": "https://learn.chatgpt.com/docs/non-interactive-mode"}
        for relative, current in replacements.items():
            with self.subTest(file=relative):
                text = (ROOT / relative).read_text(encoding="utf-8")
                self.assertIn(current, text)
                self.assertNotIn("https://learn.chatgpt.com/docs/config-basics", text)
                self.assertNotIn("https://learn.chatgpt.com/docs/noninteractive", text)


if __name__ == "__main__":
    unittest.main()
