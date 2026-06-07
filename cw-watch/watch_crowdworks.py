#!/usr/bin/env python3
from __future__ import annotations

import html
import json
import os
import re
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable
from urllib.parse import urlencode, urljoin
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parent
KEYWORDS_PATH = ROOT / "keywords.json"
SEEN_PATH = ROOT / "seen_jobs.json"
BASE_URL = "https://crowdworks.jp"
SEARCH_URL = f"{BASE_URL}/public/jobs/search"
MAX_PER_KEYWORD = int(os.getenv("CW_MAX_PER_KEYWORD", "5"))
MAX_NOTIFICATIONS = int(os.getenv("CW_MAX_NOTIFICATIONS", "8"))

HIGH_TERMS = [
    "lp",
    "ランディングページ",
    "ホームページ",
    "webサイト",
    "webディレクター",
    "制作ディレクション",
    "gas",
    "google apps script",
    "スプレッドシート",
    "chatgpt",
    "ai",
    "業務効率化",
    "業務改善",
    "web制作",
    "wordpress",
    "studio",
    "ペライチ",
]

MID_TERMS = [
    "リサーチ",
    "営業リスト",
    "リスト作成",
    "データ収集",
    "スクレイピング",
    "html",
    "css",
    "javascript",
    "php",
    "文章",
    "コピー",
]

LOW_OR_RISK_TERMS = [
    "完全成果報酬",
    "成果報酬",
    "line",
    "ライン",
    "公式line",
    "初心者歓迎",
    "未経験歓迎",
    "誰でも",
    "簡単作業",
    "スキマ時間",
    "データ入力",
    "無料",
    "モニター",
    "感想",
    "講座",
    "情報商材",
    "アカウント",
    "本人確認",
    "購入代行",
]


@dataclass
class Job:
    title: str
    url: str
    keyword: str
    search_url: str
    detail_text: str
    budget: str
    applicants: str
    posted: str
    priority: str
    reason: str
    caution: str


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def load_json(path: Path, default: dict) -> dict:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return default


def save_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def fetch(url: str) -> str:
    req = Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; damono-cw-watch/1.0; +https://makodamono.github.io/github.io/portfolio/)",
            "Accept-Language": "ja,en-US;q=0.8,en;q=0.6",
        },
    )
    with urlopen(req, timeout=20) as res:
        charset = res.headers.get_content_charset() or "utf-8"
        return res.read().decode(charset, errors="replace")


def strip_tags(value: str) -> str:
    value = re.sub(r"<script[\s\S]*?</script>", " ", value, flags=re.I)
    value = re.sub(r"<style[\s\S]*?</style>", " ", value, flags=re.I)
    value = re.sub(r"<[^>]+>", " ", value)
    value = html.unescape(value)
    return re.sub(r"\s+", " ", value).strip()


def search_url(keyword: str) -> str:
    query = urlencode(
        {
            "search[keywords]": keyword,
            "keep_search_criteria": "true",
            "order": "new",
            "hide_expired": "false",
        }
    )
    return f"{SEARCH_URL}?{query}"


def extract_job_urls(search_html: str) -> list[str]:
    urls: list[str] = []
    seen_ids: set[str] = set()
    for match in re.finditer(r"(?:https?://crowdworks\.jp)?/public/jobs/(\d+)", search_html):
        job_id = match.group(1)
        if job_id in seen_ids:
            continue
        seen_ids.add(job_id)
        urls.append(f"{BASE_URL}/public/jobs/{job_id}")
    return urls


def extract_title(page_html: str) -> str:
    h1 = re.search(r"<h1[^>]*>([\s\S]*?)</h1>", page_html, flags=re.I)
    if h1:
        title = strip_tags(h1.group(1))
        if title:
            return title
    title = re.search(r"<title[^>]*>([\s\S]*?)</title>", page_html, flags=re.I)
    if title:
        return strip_tags(title.group(1)).split("|")[0].strip()
    return "タイトル取得不可"


def extract_first(patterns: Iterable[str], text: str) -> str:
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.I)
        if match:
            return match.group(1).strip()
    return "不明"


def extract_budget(text: str) -> str:
    return extract_first(
        [
            r"(?:固定報酬|予算|報酬|契約金額)[^\d￥¥]{0,20}([￥¥]?\s?[\d,]+(?:\s?[〜~\-]\s?[￥¥]?\s?[\d,]+)?\s?円?)",
            r"([￥¥]\s?[\d,]+(?:\s?[〜~\-]\s?[￥¥]?\s?[\d,]+)?)",
            r"([\d,]+\s?円\s?[〜~\-]\s?[\d,]+\s?円)",
        ],
        text,
    )


def extract_applicants(text: str) -> str:
    return extract_first([r"応募(?:した人|人数)?[^\d]{0,12}(\d+\s?人)", r"応募者[^\d]{0,12}(\d+\s?人)"], text)


def extract_posted(text: str) -> str:
    return extract_first([r"(掲載日|投稿日|募集開始)[^\d]{0,12}([^。｜|]{4,30})"], text)


def score_job(title: str, detail_text: str, keyword: str, budget: str) -> tuple[str, str, str]:
    blob = f"{title} {detail_text} {keyword}".lower()
    risk_hits = [term for term in LOW_OR_RISK_TERMS if term.lower() in blob]
    high_hits = [term for term in HIGH_TERMS if term.lower() in blob]
    mid_hits = [term for term in MID_TERMS if term.lower() in blob]

    caution = "特になし"
    if risk_hits:
        caution = f"注意ワード: {', '.join(risk_hits[:4])}"

    numeric_budget = 0
    nums = [int(n.replace(",", "")) for n in re.findall(r"[\d,]+", budget)]
    if nums:
        numeric_budget = max(nums)

    if risk_hits:
        priority = "低"
        reason = "注意ワードが含まれるため、応募前に内容確認が必要です。"
    elif high_hits and (numeric_budget >= 10000 or budget == "不明"):
        priority = "高"
        reason = f"得意領域と一致: {', '.join(high_hits[:4])}"
    elif high_hits or mid_hits:
        priority = "中"
        terms = high_hits or mid_hits
        reason = f"対応可能領域と近い: {', '.join(terms[:4])}"
    else:
        priority = "低"
        reason = "検索語には一致しましたが、強いマッチ理由は薄めです。"

    return priority, reason, caution


def collect_jobs(keywords: list[str], seen: dict) -> list[Job]:
    jobs: list[Job] = []
    collected_urls: set[str] = set()

    for keyword in keywords:
        url = search_url(keyword)
        try:
            page = fetch(url)
        except Exception as exc:
            print(f"[warn] search failed keyword={keyword}: {exc}", file=sys.stderr)
            continue

        job_urls = extract_job_urls(page)
        print(f"[info] keyword={keyword} found_urls={len(job_urls)}")

        for job_url in job_urls[:MAX_PER_KEYWORD]:
            if job_url in seen or job_url in collected_urls:
                print(f"[info] skipped duplicate url={job_url}")
                continue
            collected_urls.add(job_url)

            time.sleep(1.0)
            try:
                detail_html = fetch(job_url)
            except Exception as exc:
                print(f"[warn] detail failed url={job_url}: {exc}", file=sys.stderr)
                continue

            title = extract_title(detail_html)
            text = strip_tags(detail_html)
            budget = extract_budget(text)
            applicants = extract_applicants(text)
            posted = extract_posted(text)
            priority, reason, caution = score_job(title, text, keyword, budget)
            print(f"[info] scored priority={priority} keyword={keyword} title={title[:80]}")
            if priority == "低":
                continue
            jobs.append(
                Job(
                    title=title,
                    url=job_url,
                    keyword=keyword,
                    search_url=url,
                    detail_text=text[:1000],
                    budget=budget,
                    applicants=applicants,
                    posted=posted,
                    priority=priority,
                    reason=reason,
                    caution=caution,
                )
            )
            if len(jobs) >= MAX_NOTIFICATIONS:
                return jobs
    return jobs


def slack_payload(jobs: list[Job]) -> dict:
    if not jobs:
        return {"text": "クラウドワークス案件監視: 新規の高/中優先度案件なし"}

    blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": f"クラウドワークス応募候補 {len(jobs)}件", "emoji": True},
        }
    ]
    for job in jobs:
        text = (
            f"*<{job.url}|{job.title[:90]}>*\n"
            f"優先度: *{job.priority}* / 検索語: `{job.keyword}`\n"
            f"報酬: {job.budget} / 応募人数: {job.applicants} / 掲載: {job.posted}\n"
            f"応募理由: {job.reason}\n"
            f"注意点: {job.caution}\n"
            f"応募文: このURLをCodexに貼って「応募文作って」でOK"
        )
        blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": text}})
        blocks.append({"type": "divider"})
    return {"text": f"クラウドワークス応募候補 {len(jobs)}件", "blocks": blocks[:45]}


def notify_slack(payload: dict) -> None:
    webhook = os.getenv("SLACK_WEBHOOK_URL")
    if payload.get("empty") and os.getenv("CW_NOTIFY_EMPTY", "false").lower() != "true":
        print("[info] no new jobs. Slack notification skipped.")
        return
    if not webhook:
        print("[info] SLACK_WEBHOOK_URL is not set. Skipping notification.")
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return

    body = json.dumps(payload).encode("utf-8")
    req = Request(webhook, data=body, headers={"Content-Type": "application/json"}, method="POST")
    with urlopen(req, timeout=20) as res:
        if res.status >= 300:
            raise RuntimeError(f"Slack notification failed: {res.status}")


def main() -> int:
    keywords_data = load_json(KEYWORDS_PATH, {"keywords": []})
    keywords = [str(k).strip() for k in keywords_data.get("keywords", []) if str(k).strip()]
    if not keywords:
        print("No keywords configured.", file=sys.stderr)
        return 1

    seen_data = load_json(SEEN_PATH, {"seen": {}})
    seen = seen_data.setdefault("seen", {})

    jobs = collect_jobs(keywords, seen)
    payload = slack_payload(jobs)
    if not jobs:
        payload["empty"] = True
    notify_slack(payload)

    for job in jobs:
        seen[job.url] = {
            "title": job.title,
            "keyword": job.keyword,
            "priority": job.priority,
            "notified_at": now_iso(),
        }

    # Keep state compact.
    if len(seen) > 500:
        items = list(seen.items())[-500:]
        seen_data["seen"] = dict(items)

    save_json(SEEN_PATH, seen_data)
    print(f"notified={len(jobs)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
