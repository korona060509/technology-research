import urllib.request
import json
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime

JST = timezone(timedelta(hours=9))

RSS_FEEDS = {
    "whats_new": "https://aws.amazon.com/about-aws/whats-new/recent/feed/",
    "aws_blog": "https://aws.amazon.com/blogs/aws/feed/",
    "security_blog": "https://aws.amazon.com/blogs/security/feed/",
}


def fetch_rss(url):
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "DiscordBot (https://github.com, 1.0)"}
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read()


def parse_items(xml_data, hours=24):
    """RSSのXMLをパースし、直近24時間以内の記事を全件返す"""
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
            # descriptionタグからHTMLタグを除去して取得
            description = item.findtext("description", "").strip()
            items.append({
                "title": item.findtext("title", "").strip(),
                "link": item.findtext("link", "").strip(),
                "pubDate": pub_date.astimezone(JST).strftime("%Y-%m-%d %H:%M JST"),
                "description": description,
            })
    return items


def main():
    result = {}

    for key, url in RSS_FEEDS.items():
        try:
            items = parse_items(fetch_rss(url))
            result[key] = items
            print(f"{key}: {len(items)}件取得")
        except Exception as e:
            result[key] = []
            print(f"[ERROR] {key}: {e}")

    with open("aws_data.json", "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print("aws_data.json に保存しました")


if __name__ == "__main__":
    main()
