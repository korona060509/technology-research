import urllib.request
import json
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime

JST = timezone(timedelta(hours=9))

ATOM_NS = "http://www.w3.org/2005/Atom"

RSS_FEEDS = {
    "anthropic_news": "https://www.anthropic.com/rss.xml",
}

ATOM_FEEDS = {
    "claude_code": "https://github.com/anthropics/claude-code/releases.atom",
    "sdk_python": "https://github.com/anthropics/anthropic-sdk-python/releases.atom",
    "sdk_js": "https://github.com/anthropics/anthropic-sdk-js/releases.atom",
}


def fetch_feed(url):
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "DiscordBot (https://github.com, 1.0)"}
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read()


def parse_rss_items(xml_data, hours=24):
    """RSS形式のXMLをパースし、直近24時間以内の記事を返す"""
    root = ET.fromstring(xml_data)
    channel = root.find("channel")
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=hours)

    items = []
    for item in channel.findall("item"):
        pub_date_str = item.findtext("pubDate")
        if not pub_date_str:
            continue
        try:
            pub_date = parsedate_to_datetime(pub_date_str)
        except Exception:
            continue
        if pub_date >= cutoff:
            description = item.findtext("description", "").strip()
            items.append({
                "title": item.findtext("title", "").strip(),
                "link": item.findtext("link", "").strip(),
                "pubDate": pub_date.astimezone(JST).strftime("%Y-%m-%d %H:%M JST"),
                "description": description,
            })
    return items


def parse_atom_items(xml_data, hours=24):
    """Atom形式のXMLをパースし、直近24時間以内のエントリを返す"""
    root = ET.fromstring(xml_data)
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=hours)

    items = []
    for entry in root.findall(f"{{{ATOM_NS}}}entry"):
        published_str = entry.findtext(f"{{{ATOM_NS}}}published") or \
                        entry.findtext(f"{{{ATOM_NS}}}updated")
        if not published_str:
            continue
        try:
            pub_date = datetime.fromisoformat(published_str.replace("Z", "+00:00"))
        except Exception:
            continue
        if pub_date >= cutoff:
            link_el = entry.find(f"{{{ATOM_NS}}}link")
            link = link_el.get("href", "") if link_el is not None else ""
            content = entry.findtext(f"{{{ATOM_NS}}}content") or \
                      entry.findtext(f"{{{ATOM_NS}}}summary") or ""
            items.append({
                "title": entry.findtext(f"{{{ATOM_NS}}}title", "").strip(),
                "link": link.strip(),
                "pubDate": pub_date.astimezone(JST).strftime("%Y-%m-%d %H:%M JST"),
                "description": content.strip(),
            })
    return items


def main():
    result = {}

    for key, url in RSS_FEEDS.items():
        try:
            items = parse_rss_items(fetch_feed(url))
            result[key] = items
            print(f"{key}: {len(items)}件取得")
        except Exception as e:
            result[key] = []
            print(f"[ERROR] {key}: {e}")

    for key, url in ATOM_FEEDS.items():
        try:
            items = parse_atom_items(fetch_feed(url))
            result[key] = items
            print(f"{key}: {len(items)}件取得")
        except Exception as e:
            result[key] = []
            print(f"[ERROR] {key}: {e}")

    with open("claude_data.json", "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print("claude_data.json に保存しました")


if __name__ == "__main__":
    main()
