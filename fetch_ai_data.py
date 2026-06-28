"""
生成AI・LLMトレンド収集スクリプト

公式の製品発表ではなく、コミュニティで話題になっている記事・著名ブログの考察を
「人気度しきい値（厳選）」で絞り込んで収集する。
結果は ai_data.json に保存する。

使い方: python3 fetch_ai_data.py
"""
import json
import re
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime

JST = timezone(timedelta(hours=9))
ATOM_NS = "http://www.w3.org/2005/Atom"
HATENA_NS = "http://www.hatena.ne.jp/info/xmlns#"

# ===== 調整パラメータ（しきい値：厳しめ／厳選）=====
# 人気度（いいね/ブクマ/ポイント）は時間をかけて溜まるため、
# 「直近1週間で人気化したトレンド」を対象にする。
WINDOW_HOURS = 168         # 何時間以内に話題化した記事を対象にするか（=7日）
QIITA_MIN_STOCKS = 50      # Qiita: ストック数の下限
HN_MIN_POINTS = 100        # Hacker News: ポイントの下限
ZENN_MIN_LIKES = 80        # Zenn: いいね数の下限
HATENA_MIN_USERS = 50      # はてなブックマーク: ブックマークユーザー数の下限

UA = {"User-Agent": "DiscordBot (https://github.com, 1.0)"}

QIITA_TAGS = ["LLM", "生成AI", "ChatGPT", "Claude", "AIエージェント"]
ZENN_TOPICS = ["llm", "生成ai", "chatgpt", "claude", "ai", "machinelearning"]
HN_QUERIES = ["LLM", "AI agent", "Claude AI", "GPT", "AI coding"]
HATENA_QUERIES = ["生成AI", "LLM", "AIエージェント", "ChatGPT"]

# 著名ブログ（厳選済みなので人気フィルタなし・直近分は全採用）
BLOG_ATOM = {
    "simon_willison": "https://simonwillison.net/atom/everything/",
}
BLOG_RSS = {
    "addy_osmani": "https://addyosmani.com/feed.xml",
}


def now_utc():
    return datetime.now(timezone.utc)


def cutoff():
    return now_utc() - timedelta(hours=WINDOW_HOURS)


def fetch(url, timeout=30):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def jst_str(dt):
    return dt.astimezone(JST).strftime("%Y-%m-%d %H:%M JST")


# ---------- Qiita ----------
def fetch_qiita():
    items = []
    seen = set()
    date_from = (now_utc() - timedelta(hours=WINDOW_HOURS)).strftime("%Y-%m-%d")
    for tag in QIITA_TAGS:
        query = f"tag:{tag} stocks:>{QIITA_MIN_STOCKS} created:>={date_from}"
        url = "https://qiita.com/api/v2/items?per_page=20&query=" + urllib.parse.quote(query)
        try:
            data = json.loads(fetch(url))
        except Exception as e:
            print(f"[ERROR] qiita({tag}): {e}")
            continue
        for it in data:
            link = it.get("url", "")
            if not link or link in seen:
                continue
            seen.add(link)
            items.append({
                "title": it.get("title", "").strip(),
                "link": link,
                "metric": f"👍{it.get('likes_count', 0)} / 🔖50+",
                "pubDate": it.get("created_at", ""),
            })
    print(f"qiita: {len(items)}件")
    return items


# ---------- Zenn ----------
def fetch_zenn():
    items = []
    seen = set()
    cut = cutoff()
    for topic in ZENN_TOPICS:
        # order=weekly は週間トレンド（いいね順）。新着すぎていいねが付く前の記事を避ける。
        url = "https://zenn.dev/api/articles?order=weekly&count=50&topicname=" + urllib.parse.quote(topic)
        try:
            data = json.loads(fetch(url))
        except Exception as e:
            print(f"[ERROR] zenn({topic}): {e}")
            continue
        for a in data.get("articles", []):
            liked = a.get("liked_count", 0)
            if liked < ZENN_MIN_LIKES:
                continue
            pub_raw = a.get("published_at") or ""
            try:
                pub = datetime.fromisoformat(pub_raw.replace("Z", "+00:00"))
            except Exception:
                continue
            if pub < cut:
                continue
            path = a.get("path", "")
            link = "https://zenn.dev" + path
            if link in seen:
                continue
            seen.add(link)
            items.append({
                "title": a.get("title", "").strip(),
                "link": link,
                "metric": f"👍{liked}",
                "pubDate": jst_str(pub),
            })
    print(f"zenn: {len(items)}件")
    return items


# ---------- Hacker News (hnrss) ----------
def fetch_hn():
    items = []
    seen = set()
    cut = cutoff()
    for q in HN_QUERIES:
        url = (f"https://hnrss.org/newest?q={urllib.parse.quote(q)}"
               f"&points={HN_MIN_POINTS}&count=20")
        try:
            xml_data = fetch(url)
            root = ET.fromstring(xml_data)
        except Exception as e:
            print(f"[ERROR] hn({q}): {e}")
            continue
        channel = root.find("channel")
        if channel is None:
            continue
        for item in channel.findall("item"):
            link = (item.findtext("link") or "").strip()
            if not link or link in seen:
                continue
            pub_raw = item.findtext("pubDate")
            try:
                pub = parsedate_to_datetime(pub_raw)
            except Exception:
                continue
            if pub < cut:
                continue
            desc = item.findtext("description") or ""
            m = re.search(r"Points:\s*(\d+)", desc)
            points = m.group(1) if m else f"{HN_MIN_POINTS}+"
            seen.add(link)
            items.append({
                "title": (item.findtext("title") or "").strip(),
                "link": link,
                "metric": f"🔺{points}pt",
                "pubDate": jst_str(pub),
            })
    print(f"hackernews: {len(items)}件")
    return items


# ---------- はてなブックマーク ----------
def fetch_hatena():
    items = []
    seen = set()
    cut = cutoff()
    date_begin = (now_utc().astimezone(JST) - timedelta(hours=WINDOW_HOURS)).strftime("%Y-%m-%d")
    for q in HATENA_QUERIES:
        # date_begin で直近に限定（デフォルトは過去5年の人気順になってしまうため）
        url = (f"https://b.hatena.ne.jp/q/{urllib.parse.quote(q)}"
               f"?target=text&sort=popular&users={HATENA_MIN_USERS}"
               f"&date_begin={date_begin}&mode=rss")
        try:
            xml_data = fetch(url)
            root = ET.fromstring(xml_data)
        except Exception as e:
            print(f"[ERROR] hatena({q}): {e}")
            continue
        # はてブのRSSはRDF(rss1.0)形式。item要素を名前空間を無視して走査する
        for item in root.iter():
            if not item.tag.endswith("item"):
                continue
            title = ""
            link = ""
            count = ""
            pub = None
            for child in item:
                tag = child.tag.split("}")[-1]
                if tag == "title":
                    title = (child.text or "").strip()
                elif tag == "link":
                    link = (child.text or "").strip()
                elif tag == "bookmarkcount":
                    count = (child.text or "").strip()
                elif tag == "date":
                    try:
                        pub = datetime.fromisoformat((child.text or "").replace("Z", "+00:00"))
                    except Exception:
                        pub = None
            if not link or link in seen:
                continue
            if pub is not None and pub < cut:
                continue
            seen.add(link)
            items.append({
                "title": title,
                "link": link,
                "metric": f"🔖{count}users" if count else "🔖人気",
                "pubDate": jst_str(pub) if pub else "",
            })
    print(f"hatena: {len(items)}件")
    return items


# ---------- 著名ブログ ----------
def fetch_blogs():
    items = []
    cut = cutoff()

    for key, url in BLOG_ATOM.items():
        try:
            root = ET.fromstring(fetch(url))
        except Exception as e:
            print(f"[ERROR] blog({key}): {e}")
            continue
        for entry in root.findall(f"{{{ATOM_NS}}}entry"):
            pub_raw = (entry.findtext(f"{{{ATOM_NS}}}published")
                       or entry.findtext(f"{{{ATOM_NS}}}updated") or "")
            try:
                pub = datetime.fromisoformat(pub_raw.replace("Z", "+00:00"))
            except Exception:
                continue
            if pub < cut:
                continue
            link_el = entry.find(f"{{{ATOM_NS}}}link")
            link = link_el.get("href", "") if link_el is not None else ""
            items.append({
                "title": (entry.findtext(f"{{{ATOM_NS}}}title") or "").strip(),
                "link": link.strip(),
                "metric": f"📝{key}",
                "pubDate": jst_str(pub),
            })

    for key, url in BLOG_RSS.items():
        try:
            root = ET.fromstring(fetch(url))
            channel = root.find("channel")
        except Exception as e:
            print(f"[ERROR] blog({key}): {e}")
            continue
        if channel is None:
            continue
        for item in channel.findall("item"):
            pub_raw = item.findtext("pubDate")
            try:
                pub = parsedate_to_datetime(pub_raw)
            except Exception:
                continue
            if pub < cut:
                continue
            items.append({
                "title": (item.findtext("title") or "").strip(),
                "link": (item.findtext("link") or "").strip(),
                "metric": f"📝{key}",
                "pubDate": jst_str(pub),
            })
    print(f"blogs: {len(items)}件")
    return items


def main():
    result = {
        "_meta": {
            "generated_at": jst_str(now_utc()),
            "window_hours": WINDOW_HOURS,
            "thresholds": {
                "qiita_stocks": QIITA_MIN_STOCKS,
                "hn_points": HN_MIN_POINTS,
                "zenn_likes": ZENN_MIN_LIKES,
                "hatena_users": HATENA_MIN_USERS,
            },
        },
        "qiita": [],
        "zenn": [],
        "hackernews": [],
        "hatena": [],
        "blogs": [],
    }

    for key, fn in (
        ("qiita", fetch_qiita),
        ("zenn", fetch_zenn),
        ("hackernews", fetch_hn),
        ("hatena", fetch_hatena),
        ("blogs", fetch_blogs),
    ):
        try:
            result[key] = fn()
        except Exception as e:
            print(f"[ERROR] {key}: {e}")
            result[key] = []

    with open("ai_data.json", "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    total = sum(len(result[k]) for k in ("qiita", "zenn", "hackernews", "hatena", "blogs"))
    print(f"ai_data.json に保存しました（合計 {total} 件）")


if __name__ == "__main__":
    main()
