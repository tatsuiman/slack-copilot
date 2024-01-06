import os
import re
import logging
from tempfile import mkdtemp
from slacklib import get_canvas_content

PRIORITY = 0
DESCRIPTION = "SlackのURLからチャンネルのCanvasを取得する"


def extract_slack_url(url):
    canvas_content = ""
    try:
        # URLからチャンネルIDとメッセージのタイムスタンプを抽出
        url_pattern = r"slack\.com/archives/([A-Z0-9]+)/p(\d{10})(\d{6})"
        matches = re.findall(url_pattern, url)
        for match in matches:
            channel_id = match[0]
            if channel_id:
                canvas_content = get_canvas_content(channel_id)
    except Exception as e:
        logging.error(f"Failed to extract slack url: {str(e)}")
    return canvas_content


def run(event):
    files = []
    processed = False
    message = event["text"]
    canvas_content = extract_slack_url(message)
    if len(canvas_content) > 10:
        processed = True
        canvas_file = os.path.join(mkdtemp(), "canvas.md")
        with open(canvas_file, "w") as f:
            f.write(canvas_content)
        files.append(canvas_file)
    return event, files, processed
