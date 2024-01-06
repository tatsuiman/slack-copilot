import os
import re
import logging
import requests
from bs4 import BeautifulSoup
from tempfile import mkdtemp
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

# 環境変数からボットのユーザーIDを取得する
SLACK_USER_TOKEN = os.getenv("SLACK_USER_TOKEN")
slack_user_client = WebClient(token=SLACK_USER_TOKEN, timeout=300)
SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")
slack_bot_client = WebClient(token=SLACK_BOT_TOKEN, timeout=300)
auth_response = slack_bot_client.auth_test()
BOT_USER_ID = auth_response["user_id"]


def get_user_id(user_id):
    return slack_bot_client.users_info(user=user_id)


def get_slack_file_bytes(file_url) -> bytes:
    r = requests.get(file_url, headers={"Authorization": f"Bearer {SLACK_BOT_TOKEN}"})
    return r.content


def update_message(channel_id, message_ts, text="", blocks=[]):
    response = None
    try:
        response = slack_bot_client.chat_update(
            channel=channel_id, ts=message_ts, text=text, blocks=blocks
        )
    except SlackApiError as e:
        logging.error(f"失敗しました: {str(e)}")
    return response


def upload_file(file, filename):
    upload = slack_bot_client.files_upload(file=file, filename=filename)
    return upload["file"]["permalink"]


def post_message(channel_id, thread_ts, text="", files=[], blocks=[]):
    response = None
    try:
        for file in files:
            filename = os.path.basename(file)
            permalink = upload_file(file, filename)
            text = text + f"\n<{permalink}|{filename}>"
        response = slack_bot_client.chat_postMessage(
            channel=channel_id, text=text, thread_ts=thread_ts, blocks=blocks
        )
    except SlackApiError as e:
        logging.error(f"失敗しました: {str(e)}")
    return response


def post_ephemeral(channel_id, thread_ts, user_id, text="", blocks=[]):
    response = None
    try:
        response = slack_bot_client.chat_postEphemeral(
            channel=channel_id,
            user=user_id,
            text=text,
            thread_ts=thread_ts,
            blocks=blocks,
        )
    except SlackApiError as e:
        logging.error(f"失敗しました: {str(e)}")
    return response


def delete_message(channel_id, message_ts):
    try:
        response = slack_bot_client.chat_delete(channel=channel_id, ts=message_ts)
        logging.info("Message deleted successfully.")
    except SlackApiError as e:
        logging.error(f"Failed to delete message: {str(e)}")


def add_reaction(name, channel_id, message_ts):
    try:
        if channel_id is not None and message_ts is not None:
            response = slack_bot_client.reactions_add(
                name=name, channel=channel_id, timestamp=message_ts
            )
            logging.info(f"Added {name} reaction")
    except SlackApiError as e:
        logging.info(f"Failed to add {name} reaction: {str(e)}")


def extract_msg_file(msg):
    messages = ""
    files = []
    # ファイルタイプがテキストならダウンロードする
    for file in msg.get("files", []):
        url_private = file["url_private_download"]
        filetype = file["filetype"]
        filename = file["name"]
        file_data = get_slack_file_bytes(url_private)
        if file["mimetype"] == "text/plain":
            messages += f"{file_data.decode()}\n"
        download_file = os.path.join(mkdtemp(), filename)
        files.append(download_file)
        with open(download_file, "wb") as f:
            f.write(file_data)
    return messages, files


def get_thread_messages(channel_id, thread_ts):
    # すべてのメッセージを保持するリスト
    all_messages = []

    try:
        # 最初のAPIリクエスト
        response = slack_bot_client.conversations_replies(
            channel=channel_id, ts=thread_ts
        )

        while True:
            # スレッドのメッセージを取得
            messages = response.get("messages", [])
            all_messages.extend(messages)

            # ページネーションチェック
            response_metadata = response.get("response_metadata", {})
            next_cursor = response_metadata.get("next_cursor")
            if not next_cursor:
                break  # 最後のページならループを抜ける

            # 次のページのリクエスト
            response = slack_bot_client.conversations_replies(
                channel=channel_id, ts=thread_ts, cursor=next_cursor
            )

    except SlackApiError as e:
        logging.error(
            f"Error fetching conversations: {e} , channel: {channel_id}, ts: {thread_ts}"
        )

    return all_messages


def get_canvas_content(channel_id):
    try:
        # チャンネルの情報を取得
        canvas_content = ""
        response = slack_bot_client.conversations_info(channel=channel_id)
        channel_info = response["channel"]
        canvas = channel_info.get("properties", {}).get("canvas", {})
        if canvas.get("is_empty", True) == False:
            file_id = canvas["file_id"]
            # file_idを使ってcanvasをダウンロード
            file_response = slack_bot_client.api_call(
                api_method="files.info", http_verb="GET", params={"file": file_id}
            )
            if file_response["ok"]:
                file_content = requests.get(
                    file_response["file"]["url_private"],
                    headers={"Authorization": f"Bearer {SLACK_BOT_TOKEN}"},
                ).content
                # HTMLのリストアイテムをMarkdownのリストアイテムに変換
                soup = BeautifulSoup(file_content, "html.parser")
                for li in soup.find_all("li"):
                    li.replace_with(f"* {li.text}")
                # HTMLの見出しをMarkdownの見出しに変換
                for h1 in soup.find_all("h1"):
                    h1.replace_with(f"# {h1.text}")
                for h2 in soup.find_all("h2"):
                    h2.replace_with(f"## {h2.text}")
                for h3 in soup.find_all("h3"):
                    h3.replace_with(f"### {h3.text}")
                for ol in soup.find_all("ol"):
                    for i, li in enumerate(ol.find_all("li")):
                        li.replace_with(f"{i+1}. {li.text}")
                for ul in soup.find_all("ul"):
                    for li in ul.find_all("li"):
                        li.replace_with(f"* {li.text}")
                canvas_content = soup.get_text().strip()
    except SlackApiError as e:
        logging.info(f"Error fetching conversation info: {e}")
    return canvas_content


def get_im_channel_id(user_id):
    channel_id = None
    response = slack_bot_client.conversations_list(types="im")
    for channel in response["channels"]:
        if channel["user"] == user_id:
            channel_id = channel["id"]
            break
    return channel_id
