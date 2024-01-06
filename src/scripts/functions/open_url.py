import re
from tools import browser_open


def run(url):
    result = ""
    ignore_domains = [
        "notion.so",
        "drive.google.com",
        "slack.com",
        "youtube.com",
        "youtu.be",
    ]
    # 特定のドメインは無視する
    for ignore_domain in ignore_domains:
        if url.find(ignore_domain) != -1:
            return "not found"
    title, content = browser_open(url)
    # タイトルの文字列をエスケープしてファイル名として有効な文字列にする
    safe_title = re.sub(r'[\\/*?:"<>|]', "", title)
    result = f"# {safe_title}\n{content}"
    return result


if __name__ == "__main__":
    # テストメッセージ
    url = "https://www.cybereason.co.jp/blog/threat-analysis-report/11356/"
    # メソッドをテスト
    r = run(url)
    print(r)
