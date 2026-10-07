"""以修改時間、登記表及本機連結檢查文件落差；Git 檢查可選用。

用法：python tools/doc-audit.py [ROOT] [--json] [--git] [--grace-seconds 2]
mtime 是待核對線索，不代表文件內容一定有錯；不修改任何檔案。
"""
import argparse
import os
from pathlib import Path
import re
import shutil
import subprocess
from urllib.parse import unquote, urlsplit
from office_common import emit
import registry

EXCLUDE = {".git", "__pycache__", "node_modules", ".venv", "venv", "scratch", "inbox", ".ai-office-state"}


def files(root):
    for folder, dirs, names in os.walk(root):
        dirs[:] = [name for name in dirs if name not in EXCLUDE and not (Path(folder) / name).is_symlink()]
        for name in names:
            path = Path(folder) / name
            if not path.is_symlink():
                yield path


def link_targets(text):
    # fenced code 中是範例，不當作文件連結。
    text = re.sub(r"(?ms)^\s*(`{3,}|~{3,})[^\n]*\n.*?^\s*\1\s*$", "", text)
    for target in re.findall(r"\[[^\]\n]*\]\(\s*(<[^>]+>|[^\s)]+)(?:\s+[^)]*)?\)", text):
        yield target.strip("<>")
    for target in re.findall(r"(?m)^\s*\[[^\]]+\]:\s*(<[^>]+>|\S+)", text):
        yield target.strip("<>")


def audit(root, include_git=False, grace=2):
    root = Path(root).resolve()
    paths = list(files(root))
    findings = []
    handoffs = [p for p in paths if p.name == "HANDOFF.md" and "templates" not in p.relative_to(root).parts]
    for handoff in handoffs:
        project = handoff.parent.parent if handoff.parent.name == "docs" else handoff.parent
        # 子專案各有 HANDOFF 時，各自核對。
        nested = [p.parent.parent if p.parent.name == "docs" else p.parent for p in handoffs if p != handoff and project in p.parents]
        newer = [p for p in paths if project in p.parents and p != handoff and not any(d == p or d in p.parents for d in nested)
                 and p.stat().st_mtime > handoff.stat().st_mtime + grace]
        if newer:
            samples = "、".join(p.relative_to(root).as_posix() for p in newer[:3])
            findings.append(f"{handoff.relative_to(root)} 之後有 {len(newer)} 個檔案修改：{samples}；建議核對交接是否需更新")
    for folder in sorted({p.parent for p in paths if p.name in ("REGISTRY.md", "INDEX.md")} | {root / "tools", root / "knowledge"}):
        if not folder.is_dir():
            continue
        mode = "knowledge" if folder.name == "knowledge" or (folder / "INDEX.md").exists() else "tools"
        target, content, errors = registry.generate(mode, folder)
        if not target.exists():
            findings.append(f"缺少 {target.relative_to(root)}，建議執行 registry.py")
        else:
            sources = [p for p in paths if folder in p.parents and p != target and (p.suffix == ".md" if mode == "knowledge" else p.suffix == ".py" and not p.name.startswith("test_"))]
            if any(p.stat().st_mtime > target.stat().st_mtime + grace for p in sources):
                findings.append(f"{target.relative_to(root)} 比來源檔案舊，建議重建")
            if target.read_text(encoding="utf-8-sig") != content:
                findings.append(f"{target.relative_to(root)} 內容與來源不一致")
        findings.extend(errors)
    for path in paths:
        if path.suffix != ".md":
            continue
        text = path.read_text(encoding="utf-8-sig", errors="replace")
        for link in link_targets(text):
            if any(mark in link for mark in ("<", ">", "${", "{{")) or link.startswith("#"):
                continue
            url = urlsplit(link)
            if url.scheme or url.netloc or not url.path:
                continue
            target = path.parent / unquote(url.path)
            if not target.exists():
                findings.append(f"{path.relative_to(root)} 的本機連結不存在：{link}")
    if include_git and shutil.which("git"):
        repos = {p.parent for p in paths if (p.parent / ".git").exists()}
        if (root / ".git").exists():
            repos.add(root)
        for repo in sorted(repos):
            for args, label in ((["status", "--porcelain"], "有未提交的檔案"), (["rev-list", "--count", "@{u}..HEAD"], "有未推送的 commit")):
                result = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, encoding="utf-8", timeout=10)
                if result.returncode == 0 and result.stdout.strip() not in ("", "0"):
                    findings.append(f"{repo.name} {label}")
    return findings


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", nargs="?", type=Path, default=Path.cwd())
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--git", action="store_true")
    parser.add_argument("--grace-seconds", type=float, default=2)
    args = parser.parse_args(argv)
    if not args.root.is_dir():
        parser.error("根目錄不存在")
    findings = audit(args.root, args.git, args.grace_seconds)
    if args.json:
        emit({"count": len(findings), "findings": findings})
    else:
        print("\n".join(findings) if findings else "未發現文件落差線索。")
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
