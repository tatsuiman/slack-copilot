import os
import re
import logging

# 補助が必要なユーザ一覧
BEGINNER_USERS = os.getenv("BEGINNER_USERS", "").split(":")

DESCRIPTION = "より詳細な質問を促すよう指示を変更"


def run(event):
    message = event["text"]
    user_id = event["user"]
    files = []

    processed = False
    if user_id in BEGINNER_USERS:
        message = f"{message}\n解答は必ず日本語で出力してください。"
        message = f"{message}\nもし質問内容に矛盾があったり、背景や文脈が足りない場合は指摘してください。"
        processed = True

    event["text"] = message
    return event, files, processed
