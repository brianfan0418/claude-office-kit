"""從 Python 檔頭或知識 frontmatter 產生工具登記表與知識索引。

用法：python tools/registry.py tools|knowledge DIR [--check]
frontmatter 支援單行 key: value；不依賴 YAML 套件，忽略測試、README、INDEX。
"""
import argparse
import ast
from pathlib import Path
import re
from urllib.parse import quote
from office_common import write_text


def frontmatter(text):
    match = re.match(r"\A---\r?\n(.*?)\r?\n---(?:\r?\n|$)", text, re.S)
    if not match:
        return {}
    return {key: value.strip().strip("\"'") for key, value in re.findall(r"^([\w-]+):\s*([^\n]*)$", match[1], re.M)}


def cell(value):
    return str(value).replace("|", "\\|").replace("\n", " ")


def generate(mode, folder, tool_paths=None):
    folder = Path(folder)
    rows, errors = [], []
    if mode == "tools":
        for path in sorted(tool_paths if tool_paths is not None else folder.glob("*.py")):
            if path.name.startswith("test_"):
                continue
            try:
                doc = ast.get_docstring(ast.parse(path.read_text(encoding="utf-8-sig"))) or ""
            except (SyntaxError, OSError) as exc:
                errors.append(f"{path.name}：{exc}")
                continue
            lines = doc.strip().splitlines()
            summary = lines[0] if lines else ""
            usage = next((line.split("：", 1)[1].strip() for line in lines if line.startswith("用法：")), "")
            if not summary or not usage:
                errors.append(f"{path.name}：檔頭缺用途或「用法：」")
            rows.append(f"| [{path.name}]({quote(path.name)}) | {cell(summary)} | {cell(usage)} |")
        title, headings, name = "工具登記表", "| 工具 | 用途 | 用法 |", "REGISTRY.md"
    else:
        for path in sorted(folder.rglob("*.md")):
            if path.name in ("INDEX.md", "README.md"):
                continue
            meta = frontmatter(path.read_text(encoding="utf-8-sig"))
            missing = [key for key in ("name", "description", "type", "status", "updated") if not meta.get(key)]
            if missing:
                errors.append(f"{path.name}：缺 {', '.join(missing)}")
            if meta.get("name") != path.stem:
                errors.append(f"{path.name}：name 應與檔名相同")
            rel = path.relative_to(folder).as_posix()
            values = [f"[{rel}]({quote(rel)})"] + [cell(meta.get(key, "")) for key in ("description", "type", "status", "updated")]
            rows.append("| " + " | ".join(values) + " |")
        title, headings, name = "知識索引", "| 文件 | 說明 | 類型 | 狀態 | 更新 |", "INDEX.md"
    text = f"# {title}\n\n由 `registry.py {mode}` 自動產生；修改來源後重跑，請勿手改。\n\n{headings}\n" + "|---|---|---|" + ("---|---|" if mode == "knowledge" else "") + "\n" + "\n".join(rows) + "\n"
    return folder / name, text, errors


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["tools", "knowledge"])
    parser.add_argument("folder", type=Path)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    if not args.folder.is_dir():
        parser.error("目錄不存在")
    target, text, errors = generate(args.mode, args.folder)
    if args.check:
        if not target.is_file() or target.read_text(encoding="utf-8") != text:
            errors.append(f"{target.name} 過期或不存在")
    elif not errors:
        write_text(target, text)
    for error in errors:
        print(error)
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
