# 参考
# https://qiita.com/seratch/items/12b39d636daf8b1e5fbf
import os
import yara
import logging
import sentry_sdk
from sentry_sdk import set_user, set_tag
from sentry_sdk.integrations.aws_lambda import AwsLambdaIntegration
from slack_sdk import WebClient
from slack_bolt import App, Ack, BoltContext, Respond
from slack_bolt.adapter.aws_lambda import SlackRequestHandler
from slack_bolt.context import BoltContext
from ui import generate_unfurl_message, generate_home, generate_select_assistant_block
from store import Assistant, get_thread_info, publish_event
from slacklib import (
    get_thread_messages,
    add_reaction,
    delete_message,
    get_im_channel_id,
    BOT_USER_ID,
)

# 環境変数からプロジェクト名と関数名を取得
BOT_NAME = os.getenv("BOT_NAME")
SLACK_SIGNING_SECRET = os.getenv("SLACK_SIGNING_SECRET")
SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")

logging.basicConfig(format="[%(levelname)s] %(message)s", level=logging.INFO)
logging.info(f"BotID:{BOT_USER_ID} BotName:{BOT_NAME}")

sentry_sdk.init(
    dsn=os.getenv("SENTRY_DSN"),
    enable_tracing=True,
    traces_sample_rate=0.1,
    profiles_sample_rate=0.1,
    integrations=[
        AwsLambdaIntegration(timeout_warning=True),
    ],
)
set_tag("botname", BOT_NAME)

headers = {"Content-Type": "application/json"}

yara_rule_file = "/function/data/auto_reply.yara"
# YARAファイルからルールをコンパイル
auto_reply_rules = yara.compile(filepath=yara_rule_file)

app = App(
    token=SLACK_BOT_TOKEN,
    signing_secret=SLACK_SIGNING_SECRET,
    # AWS Lamdba では、必ずこの設定を true にしておく必要があります
    process_before_response=True,
)


def generate_auto_reply_message(event):
    message = event.get("text", "")
    user_id = event.get("user")
    channel_id = event.get("channel")
    reply_message = ""
    if auto_reply_rules is None:
        return None
    # メッセージにマッチするルールを検索
    matches = auto_reply_rules.match(data=f"user:{user_id} message:{message}")
    if matches:
        for match in matches:
            channels = match.meta.get("channels")
            if channels is None or channel_id in channels.split(","):
                reply_message += match.meta["message"]
        if len(reply_message) > 0:
            return reply_message
    return None


@app.shortcut("update_assistant")
def shortcut_update_assistant(ack, shortcut, client):
    ack()
    client.views_open(
        trigger_id=shortcut["trigger_id"],
        # A simple view payload for a modal
        view={
            "type": "modal",
            "callback_id": "assistant-submit",
            "title": {"type": "plain_text", "text": "アシスタントの変更"},
            "close": {"type": "plain_text", "text": "Close"},
            "submit": {"type": "plain_text", "text": "update"},
            "blocks": generate_select_assistant_block(),
        },
    )


# sections ブロックの選択がされたときに呼び出されます
@app.action("assistant-select")
def handle_select_action(ack, body, logger):
    ack()


@app.view("assistant-submit")
def handle_update_assistant(ack, view, body, respond):
    ack()
    selected = None
    user_id = body["user"]["id"]
    for block_id, block in view["state"]["values"].items():
        for action_id, action in block.items():
            if action["type"] == "static_select":
                selected_option = action.get("selected_option")
                if selected_option:
                    selected = selected_option["value"]
                    assistant = Assistant(user_id)
                    assistant.update_assistant_name(selected)


@app.action("send_api_key")
def handle_send_api_key_action(ack, body, client):
    ack()
    user_id = body["user"]["id"]
    channel_id = body["channel"]["id"]
    event_ts = body["container"]["message_ts"]
    thread_ts = body["container"].get("thread_ts", event_ts)
    assistant = Assistant(user_id)
    # TextInputから入力された値を取得
    block_id = list(body["state"]["values"].keys())[0]
    api_key = body["state"]["values"][block_id]["input-api-key"]["value"]
    set_user({"id": user_id})
    if api_key is None or api_key.find("sk-") == -1:
        client.chat_postEphemeral(
            channel=channel_id,
            user=user_id,
            text=f"<@{user_id}>APIキーが不正です",
            thread_ts=thread_ts,
        )
    else:
        client.chat_postEphemeral(
            channel=channel_id,
            user=user_id,
            text=f"<@{user_id}> APIキーを設定しました。",
            thread_ts=thread_ts,
        )
        assistant.create_assistant(api_key=api_key)


@app.action("ask_button")
def handle_ask_action(ack, body, client):
    ack()
    user_id = body["user"]["id"]
    channel_id = body["channel"]["id"]
    event_ts = body["container"]["message_ts"]
    thread_ts = body["container"].get("thread_ts", event_ts)
    # TextInputから入力された値を取得
    block_id = list(body["state"]["values"].keys())[0]
    text = body["state"]["values"][block_id]["ask-action"]["value"]
    set_user({"id": user_id})
    if text is None or len(text) < 5:
        client.chat_postEphemeral(
            channel=channel_id,
            user=user_id,
            text=f"<@{user_id}>メッセージが短すぎます",
            thread_ts=thread_ts,
        )
        return
    app_unfurl_url = body["container"]["app_unfurl_url"]
    prompt = f"{text}\n{app_unfurl_url}"
    im_channel_id = get_im_channel_id(user_id)
    client.chat_postEphemeral(
        channel=channel_id,
        user=user_id,
        text=f"<@{user_id}>回答を生成しています。生成が完了したら<#{im_channel_id}>でお知らせします。",
        thread_ts=thread_ts,
    )
    res = client.chat_postMessage(
        channel=im_channel_id,
        text=f"以下のURLについての質問に回答します。\n{app_unfurl_url}\n質問内容\n```{text}```",
        thread_ts=thread_ts,
    )
    event = {
        "user": user_id,
        "type": "message",
        "channel": im_channel_id,
        "thread_ts": res["ts"],
        "text": prompt,
        "ts": res["ts"],
    }
    publish_event(event)


@app.action("faq_button_0")
@app.action("faq_button_1")
@app.action("faq_button_2")
@app.action("faq_button_3")
@app.action("faq_button_4")
def faq_button(ack: Ack, body: dict, action: dict, respond: Respond):
    ack()
    user_id = body["user"]["id"]
    channel_id = body["channel"]["id"]
    thread_ts = body["container"]["thread_ts"]
    message_ts = body["container"]["message_ts"]
    add_reaction("eyes", channel_id, message_ts)
    set_user({"id": user_id})
    event = {
        "user": user_id,
        "type": "message",
        "channel": channel_id,
        "thread_ts": thread_ts,
        "text": action["value"],
        "ts": message_ts,
    }
    publish_event(event)


@app.action("delete_button")
def delete_button(ack: Ack, body: dict, action: dict, respond: Respond):
    ack()
    user_id = body["user"]["id"]
    channel_id = body["channel"]["id"]
    message_ts = body["container"]["message_ts"]
    set_user({"id": user_id})
    delete_message(channel_id, message_ts)


@app.action("stop_button")
def delete_button(ack: Ack, body: dict, action: dict, respond: Respond):
    ack()
    respond("処理を中断しています")
    user_id = body["user"]["id"]
    channel_id = body["channel"]["id"]
    thread_ts = body["container"]["thread_ts"]
    assistant = Assistant(user_id)
    client = assistant.get_client()
    set_user({"id": user_id})
    thread_messages = get_thread_messages(channel_id, thread_ts)
    ts = thread_messages[-1]["thread_ts"]
    doc_id = f'{BOT_USER_ID}_run_{ts.replace(".", "")}'
    try:
        doc = get_thread_info(doc_id=doc_id)
        if doc is not None:
            # ドキュメントIDが存在する場合はOpenAI Thread IDを取得する
            run_id = doc.get("run_id")
            thread_id = doc.get("thread_id")
            logging.info(f"cancelling thread {doc_id}:{run_id}:{thread_id}")
            res = client.cancel_run(thread_id, run_id)
            logging.info(res)
        else:
            logging.error(f"thread_id not found. doc_id:{doc_id}")
        respond("処理を中断しました")
    except Exception as e:
        respond(f"処理の中断に失敗しました。{e}")
        logging.error(e)


@app.event("link_shared")
def handle_link_shared(event, say, ack):
    ack()
    links = event.get("links", [])
    for link in links:
        if link["domain"] in [
            "github.com",
            "notion.so",
            "youtube.com",
            "youtu.be",
        ]:
            # Unfurl用のメッセージを生成
            unfurls = {link["url"]: generate_unfurl_message()}
            # chat.unfurl APIを使用してUnfurlを行う
            client = WebClient(token=SLACK_BOT_TOKEN)
            client.chat_unfurl(
                channel=event["channel"], ts=event["message_ts"], unfurls=unfurls
            )


# App Homeが開かれたときのイベントハンドラ
@app.event("app_home_opened")
def update_home_tab(client, event, logger):
    user_id = event["user"]
    assistant = Assistant(user_id)
    assistant_name = assistant.get_assistant_name()
    payload = generate_home(assistant_name)
    client.views_publish(user_id=event["user"], view=payload)


@app.message("")
def handle_message(message, context: BoltContext, client: WebClient):
    user_id = message.get("user")
    channel_id = message.get("channel")
    event_ts = message.get("ts")
    thread_ts = message.get("thread_ts")
    channel_type = message.get("channel_type")
    set_user({"id": user_id})

    # BOTのPOSTには反応しない
    if user_id == BOT_USER_ID:
        return

    message_text = message.get("text", "")
    reply_message = generate_auto_reply_message(message)
    if reply_message is not None:
        text = f"<@{user_id}>\n{reply_message}"
        client.chat_postEphemeral(
            channel=channel_id,
            user=user_id,
            text=text,
            thread_ts=thread_ts,
        )

    # DMまたはメンション付きのメッセージでなければ無視
    if not f"<@{BOT_USER_ID}>" in message_text and channel_type != "im":
        return
    # 既読リアクション
    client.reactions_add(name="eyes", channel=channel_id, timestamp=event_ts)
    # 誤送信防止
    if len(message_text.replace(f"<@{BOT_USER_ID}>", "").strip()) < 10:
        text = f"<@{user_id}>メッセージが短すぎます。"

        client.chat_postEphemeral(
            channel=channel_id,
            user=user_id,
            text=text,
            thread_ts=thread_ts,
        )
        return
    publish_event(message)


slack_handler = SlackRequestHandler(app=app)


def handler(event, context):
    if "X-Slack-Signature" not in event["headers"]:
        return {"statusCode": 400, "body": "Verification failed"}
    try:
        res = slack_handler.handle(event, context)
        return res
    except Exception as e:
        sentry_sdk.capture_exception(e)
        logging.exception(e)
        return {"statusCode": 500, "body": "Internal Server Error"}
