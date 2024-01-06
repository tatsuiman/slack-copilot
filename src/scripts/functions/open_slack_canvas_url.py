import re
import sys, os

sys.path.append(os.path.join(os.path.dirname(__file__), "../"))
from slacklib import get_canvas_content


def extract_slack_canvas_url(url):
    messages = ""
    try:
        # URLからチャンネルIDを抽出
        url_pattern = r"slack\.com/canvas/([A-Z0-9]+)"
        matches = re.findall(url_pattern, url)
        for channel_id in matches:
            if channel_id:
                messages = get_canvas_content(channel_id)
            else:
                messages = "URLが不正です。"
    except Exception as e:
        messages = f"Failed to extract slack url: {str(e)}"
    return messages


def run(url):
    canvas_content = extract_slack_canvas_url(url)
    return canvas_content
