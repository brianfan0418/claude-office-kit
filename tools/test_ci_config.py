"""CI 設定須執行本 repo 的測試與原有外掛一致性檢查。"""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parent.parent
WORKFLOW = ROOT / ".github/workflows/ci.yml"
CLOUD_BUILD = ROOT / "cloudbuild.yaml"

TEST_COMMANDS = (
    "python -m unittest discover -s hooks",
    "python -m unittest discover -s tools",
    "python tools/build_plugin.py --check",
)
DEPENDENCIES = '"markitdown[docx,pdf]" python-docx reportlab'


class CIConfigTests(unittest.TestCase):
    def test_both_platforms_run_project_tests(self):
        for path in (WORKFLOW, CLOUD_BUILD):
            with self.subTest(platform=path):
                config = path.read_text(encoding="utf-8")
                self.assertIn(DEPENDENCIES, config)
                self.assertIn("python -m pip install", config)
                for command in TEST_COMMANDS:
                    self.assertIn(command, config)
        self.assertTrue(list((ROOT / "hooks").glob("test_*.py")))
        self.assertTrue(list((ROOT / "tools").glob("test_*.py")))

    def test_actions_runs_on_pr_and_main_push(self):
        workflow = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("pull_request:", workflow)
        self.assertIn("push:", workflow)
        self.assertIn("branches: [main]", workflow)

    def test_cloud_build_has_executable_python_step(self):
        config = CLOUD_BUILD.read_text(encoding="utf-8")
        self.assertIn("name: python:3.12", config)
        self.assertIn("name: python:3.12-slim", config)
        self.assertIn("entrypoint: sh", config)
        self.assertIn("      - -ceu", config)


if __name__ == "__main__":
    unittest.main()
