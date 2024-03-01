import os
import sys
import json
import logging
import base64
import hashlib
import sentry_sdk
from datetime import datetime
from tempfile import mkdtemp
from sentry_sdk import set_user, set_tag
from sentry_sdk.integrations.aws_lambda import AwsLambdaIntegration

logging.basicConfig(format="[%(levelname)s] %(message)s", level=logging.INFO)

from ai import generate_assistant_model, BASE_MODEL
from handle_plugin import handle_file_plugin, handle_input_plugin
from handle_assistant import handle_assistant
from store import Assistant
from slacklib import (
    add_reaction,
    post_message,
    update_message,
    get_slack_file_bytes,
    BOT_USER_ID,
)
from blockkit import (
    Input,
    Message,
    PlainTextInput,
    Button,
    Actions,
)

# 環境変数からプロジェクト名と関数名を取得
BOT_NAME = os.getenv("BOT_NAME")

# デバッグモード
DEBUG = os.getenv("DEBUG", "false").lower() == "true"

logging.info(f"[Start Function] User:{BOT_USER_ID} debug: {DEBUG}")

sentry_sdk.init(
    dsn=os.getenv("SENTRY_DSN"),
    enable_tracing=True,
    traces_sample_rate=0.1,
    profiles_sample_rate=0.1,
    integrations=[
        AwsLambdaIntegration(),
    ],
)

set_tag("botname", BOT_NAME)


def generate_api_key_input_message():
    elements = [
        Button(
            action_id="send_api_key",
            text="送信",
            value="api-key",
            style="primary",
        )
    ]
    return Message(
        blocks=[
            Input(
                element=PlainTextInput(
                    action_id="input-api-key",
                    placeholder="入力されたAPIキーは他の人からは見えません",
                ),
                label="APIキーを入力してください",
            ),
            Actions(elements=elements),
        ],
    ).build()


def handle_file_share(event):
    files = []
    # アップロードされたファイルを取得
    for file in event.get("files", []):
        url_private = file["url_private_download"]
        filename = datetime.now().strftime("%Y%m%d_") + file["name"]
        file_path = os.path.join(mkdtemp(), filename)
        file_data = get_slack_file_bytes(url_private)
        with open(file_path, "wb") as f:
            f.write(file_data)
        logging.info(f"upload: {filename}")
        files.append(file_path)
    return files


def handle_message(event):
    headers = {"Content-Type": "application/json"}
    user_id = event.get("user")
    message_text = event.get("text", "")
    channel_id = event.get("channel")
    thread_ts = event.get("thread_ts") if "thread_ts" in event else event.get("ts")
    event_ts = event.get("ts")
    subtype = event.get("subtype")
    response_files = []

    res = post_message(channel_id, event_ts, "Typing...")
    process_ts = res["ts"]
    assistant = Assistant(user_id)

    # APIキーが設定されていなければメッセージを送信する
    if (
        assistant.api_key.find("sk-") == -1
        and os.getenv("OPENAI_API_KEY").find("sk-") == -1
    ):
        payload = generate_api_key_input_message()
        update_message(channel_id, process_ts, blocks=payload["blocks"])
        return

    # プロンプトからアシスタントの設定を変更
    model = generate_assistant_model(event)
    logging.info(f"generate model: {model}")
    if model is not None:
        logging.info(f"generate model: {model}")
        response_files.extend(model.get("files", []))
        add_reaction("robot_face", channel_id, event_ts)
    else:
        model = {
            "model": BASE_MODEL,
            "instructions": "あなたはユーザに質問に回答するアシスタントです",
            "tools": [],
            "generated": False,
        }

    # メッセージからファイルを抽出
    extract_files, event = handle_input_plugin(event, process_ts)

    # ファイルアップロードイベント
    if subtype == "file_share":
        files = handle_file_share(event)
        extract_files.extend(files)

    # ファイルプラグインの実行
    extract_files, event = handle_file_plugin(event, extract_files, process_ts)
    response_files.extend(extract_files)

    # アシスタントの処理
    handle_assistant(event, process_ts, response_files, assistant, model)

    logging.info(f"response files: {response_files}")

    # 抽出されたファイルをスレッドに返信する
    if len(response_files) > 0:
        message = "以下のファイルが抽出されました。"
        # 抽出されたファイルを返信する
        post_message(channel_id, thread_ts, message, files=response_files)

    return ("", 200, headers)


message_cache = []


def handler(event, context):
    # SNSからメッセージが再送されている場合は無視
    event = json.loads(event["Records"][0]["Sns"]["Message"])
    message_text = json.dumps(event)
    message_hash = hashlib.md5(message_text.encode()).hexdigest()
    if message_hash in message_cache and len(message_text) > 0:
        return "OK"
    else:
        message_cache.append(message_hash)

    with sentry_sdk.configure_scope() as scope:
        user_id = event.get("user")
        scope.set_user({"id": user_id})
        try:
            # メッセージイベントの処理
            if event["type"] == "message":
                handle_message(event)
        except Exception as e:
            logging.error(e)
            sentry_sdk.capture_exception(e)

        scope.clear()

    return "OK"
