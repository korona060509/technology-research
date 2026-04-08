"""
Discord Webhook通知スクリプト
使い方: python3 discord_notify.py <WEBHOOK_URL> <messages.jsonのパス>
messages.jsonの形式: ["メッセージ1", "メッセージ2", ...]
"""
import sys
import json
import time
import urllib.request
import urllib.error


def send_message(webhook_url, content):
    data = json.dumps({"content": content}).encode("utf-8")
    req = urllib.request.Request(
        webhook_url,
        data=data,
        headers={
            "Content-Type": "application/json",
            "User-Agent": "DiscordBot (https://github.com, 1.0)",
        }
    )
    with urllib.request.urlopen(req) as resp:
        return resp.status


def send_messages(webhook_url, messages):
    for i, msg in enumerate(messages, 1):
        # 1900文字を超える場合は分割して送信
        chunks = [msg[j:j+1900] for j in range(0, len(msg), 1900)]
        for chunk in chunks:
            status = send_message(webhook_url, chunk)
            print(f"送信完了 ({i}/{len(messages)}): HTTP {status}")
            time.sleep(1)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("使い方: python3 discord_notify.py <WEBHOOK_URL> <messages.jsonのパス>")
        sys.exit(1)

    webhook_url = sys.argv[1]
    messages_path = sys.argv[2]

    with open(messages_path, encoding="utf-8") as f:
        messages = json.load(f)

    send_messages(webhook_url, messages)
