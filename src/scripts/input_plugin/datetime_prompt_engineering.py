import os
import re
import logging
from pytz import timezone
from datetime import datetime, timedelta

PRIORITY = 0
DESCRIPTION = "指示に日付を追加します"


def run(event):
    message = event["text"]
    files = []
    processed = False
    # メッセージに今日や今、本日のようなキーワードが含まれる場合、今日の日付を追加する
    if re.search(r"今日|本日", message):
        today = datetime.now().astimezone(tz=timezone("Asia/Tokyo"))
        message = f"{message}\n今日の日付は{today.strftime('%Y年%m月%d日')}です。"
        processed = True
    # 昨日も同じように処理します。
    if re.search(r"昨日", message):
        yesterday = datetime.now().astimezone(tz=timezone("Asia/Tokyo")) - timedelta(
            days=1
        )
        message = f"{message}\n昨日の日付は{yesterday.strftime('%Y年%m月%d日')}です。"
        processed = True

    event["text"] = message
    return event, files, processed


if __name__ == "__main__":
    r = run("昨日は何日？")
    print(r)
