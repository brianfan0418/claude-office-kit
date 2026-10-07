"""將 Anthropic、OpenAI 官方使用建議整批下載，一頁一檔並保留來源清單。

用法：python tools/official-docs-fetch.py --out DIR [--only claude-code,claude-platform,openai-codex,openai-api] [--workers 4]
來源：各官方網站 llms.txt；更新時原地替換成功頁面，失敗保留舊頁並在 manifest.json 標記。
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
from pathlib import Path
import re
from urllib.parse import urlsplit
import urllib.request
from office_common import emit, read_json, write_json, write_text

SITES = {
    "claude-code": ("https://code.claude.com/docs/llms.txt", r"/docs/en/"),
    "claude-platform": ("https://platform.claude.com/llms.txt", r"prompt-engineering/|agent-skills/|context-windows|compaction|context-editing|effort|thinking|prompt-caching|tool-use/|test-and-evaluate/"),
    "openai-codex": ("https://learn.chatgpt.com/llms.txt", r"/docs/"),
    "openai-api": ("https://developers.openai.com/api/docs/llms.txt", r"/guides/(prompt|reasoning|latest-model|agents|tools|evaluation|agent-evals|optimizing|model-selection|production-best-practices|safety-best-practices|frontend|code-generation|compaction|steering|latency|cost)")}
HOSTS = {urlsplit(index).hostname for index, _ in SITES.values()}


def get(url):
    if urlsplit(url).scheme != "https" or urlsplit(url).hostname not in HOSTS:
        raise ValueError("僅下載清單內的官方 HTTPS 網站")
    request = urllib.request.Request(url, headers={"User-Agent": "office-kit-docs/1.0"})
    with urllib.request.urlopen(request, timeout=60) as response:
        if urlsplit(response.url).hostname not in HOSTS:
            raise ValueError("官方頁面轉址到清單外網站")
        return response.read().decode("utf-8-sig", errors="replace")


def page_urls(index_text, host, keep):
    urls = set()
    for url in re.findall(r"https://[^\s)<>]+", index_text):
        parsed = urlsplit(url)
        if parsed.hostname == host and parsed.path.endswith(".md") and re.search(keep, parsed.path):
            urls.add(url)
    return sorted(urls)


def filename(url):
    base = re.sub(r"[^\w.-]", "_", urlsplit(url).path.rstrip("/").split("/")[-1])[:70]
    return base.removesuffix(".md") + "-" + hashlib.sha256(url.encode()).hexdigest()[:12] + ".md"


def full_pages(text):
    """Claude Code 官方完整文字版依標題及 Source 分頁。"""
    pages = {}
    for page in re.split(r"\n(?=# [^\n]+\nSource: )", "\n" + text):
        match = re.match(r"# [^\n]+\nSource: (\S+)", page.strip())
        if match:
            pages[match[1].removesuffix(".md")] = page.strip() + "\n"
    return pages


def fetch_site(site, dest, workers=4):
    index, keep = SITES[site]
    old = read_json(dest / "manifest.json", {}).get("pages", [])
    previous = {row["url"]: row for row in old}
    try:
        urls = page_urls(get(index), urlsplit(index).hostname, keep)
        if not urls:
            raise ValueError("官方索引未解析出符合篩選的 Markdown 頁面")
    except Exception as exc:
        write_json(dest / "manifest.json", {"site": site, "index": index, "index_error": str(exc), "pages": old})
        return {"site": site, "ok": False, "error": str(exc)}

    def one(url):
        row = {"url": url, "file": filename(url)}
        try:
            body = get(url)
            if not body.strip() or body.lstrip().lower().startswith(("<!doctype html", "<html")):
                raise ValueError("頁面為空或回傳 HTML，未覆寫舊頁")
            write_text(dest / row["file"], body)
            row.update(status="ok", fetched_at=datetime.now(timezone.utc).isoformat(), bytes=len(body.encode("utf-8")),
                       sha256=hashlib.sha256(body.encode("utf-8")).hexdigest())
        except Exception as exc:
            row = dict(previous.get(url, row), status="failed", error=str(exc))
        return row

    with ThreadPoolExecutor(max_workers=workers) as executor:
        rows = list(executor.map(one, urls))
    if site == "claude-code" and any(row["status"] == "failed" for row in rows):
        # 部分官方 .md 連結已改為 HTML 轉址；同站 llms-full.txt 仍提供該頁原文。
        combined = "https://code.claude.com/docs/llms-full.txt"
        try:
            pages = full_pages(get(combined))
            for row in rows:
                if row["status"] == "failed" and row["url"].removesuffix(".md") in pages:
                    body = pages[row["url"].removesuffix(".md")]
                    write_text(dest / row["file"], body)
                    row.pop("error", None)
                    row.update(status="ok", fetched_from=combined, fetched_at=datetime.now(timezone.utc).isoformat(),
                               bytes=len(body.encode("utf-8")), sha256=hashlib.sha256(body.encode("utf-8")).hexdigest())
        except Exception:
            pass  # 保留原始頁面的失敗原因與舊檔，不宣稱更新成功。
    rows += [dict(row, status="removed-from-index") for url, row in previous.items() if url not in urls]
    write_json(dest / "manifest.json", {"site": site, "index": index, "pages": rows})
    failed = sum(row["status"] == "failed" for row in rows)
    return {"site": site, "ok": failed == 0, "pages": len(urls), "failed": failed}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--only", default=",".join(SITES))
    parser.add_argument("--workers", type=int, choices=range(1, 9), default=4)
    args = parser.parse_args(argv)
    sites = args.only.split(",")
    if any(site not in SITES for site in sites):
        parser.error("--only 請使用已列出的來源名稱")
    args.out.mkdir(parents=True, exist_ok=True)
    lock = args.out / ".fetch.lock"
    try:
        lock.mkdir()
    except FileExistsError:
        emit({"ok": False, "error": "此輸出位置正在更新或上次中斷；請核對 .fetch.lock/owner.json 後再重跑"})
        return 1
    try:
        import os
        write_json(lock / "owner.json", {"pid": os.getpid()})
        results = [fetch_site(site, args.out / site, args.workers) for site in sites]
        emit({"ok": all(row["ok"] for row in results), "results": results})
        return 0 if all(row["ok"] for row in results) else 1
    finally:
        (lock / "owner.json").unlink(missing_ok=True)
        lock.rmdir()


if __name__ == "__main__":
    raise SystemExit(main())
