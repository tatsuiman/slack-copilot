import os
import sys
import re
import logging

sys.path.append(os.path.join(os.path.dirname(__file__), "../"))
from slacklib import get_thread_messages


def extract_slack_url(url):
    messages = ""
    try:
        # URLからチャンネルIDとメッセージのタイムスタンプを抽出
        url_pattern = r"slack\.com/archives/([A-Z0-9]+)/p(\d{10})(\d{6})"
        matches = re.findall(url_pattern, url)
        for match in matches:
            channel_id = match[0]
            thread_ts = match[1] + "." + match[2]
            if channel_id:
                thread_messages = get_thread_messages(channel_id, thread_ts)
                logging.info(f"[{channel_id}] {len(thread_messages)} messages")
                if len(thread_messages) > 0:
                    for msg in thread_messages:
                        # 各メッセージのユーザーIDとテキストを出力
                        user_id = msg.get("user")
                        message_text = msg.get("text")
                        messages += f"* <@{user_id}>: {message_text}\n"
                else:
                    messages = "メッセージが取得できません。チャンネルに参加していないかもしれません。"
            else:
                messages = "URLが不正です。"
    except Exception as e:
        messages = f"Failed to extract slack url: {str(e)}"
    return messages


def run(url):
    message = ""
    message_history = extract_slack_url(url)
    if len(message_history) > 0:
        message = f"# チャット履歴\n{message_history}"
    return message
