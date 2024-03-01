# 参考
# https://qiita.com/seratch/items/12b39d636daf8b1e5fbf
import os
import yara
import plyara
import yaml
import logging
import sentry_sdk
from tempfile import mkdtemp
from sentry_sdk import set_user, set_tag
from sentry_sdk.integrations.aws_lambda import AwsLambdaIntegration
from slack_sdk import WebClient
from slack_bolt import App, Ack, BoltContext, Respond
from slack_bolt.adapter.aws_lambda import SlackRequestHandler
from slack_bolt.context import BoltContext
from blockkit import (
    Divider,
    Input,
    Message,
    PlainTextInput,
    Button,
    Actions,
    Home,
    Header,
    Section,
)
from tools import add_notion_page, truncate_strings
from ai import CODE_INTERPRETER_EXTS
from store import Assistant
from store import get_thread_info, publish_event
from slacklib import (
    get_thread_messages,
    get_slack_file_bytes,
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


def generate_unfurl_message():
    elements = [
        Button(
            action_id="ask_button",
            text="送信",
            value="ask",
            style="primary",
        )
    ]
    return Message(
        blocks=[
            Input(
                element=PlainTextInput(
                    action_id="ask-action",
                    placeholder="質問や回答内容が他の人に見られる心配はありません",
                ),
                label="リンクの内容についてAIに質問してみましょう",
            ),
            Actions(elements=elements),
        ],
    ).build()


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
    text = body["state"]["values"][block_id]["input-api-key"]["value"]
    set_user({"id": user_id})
    if text is None or text.find("sk-") == -1:
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
        assistant.set_api_key(api_key=text)
        assistant.create_assistant()


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


@app.action("contradiction_button")
def contradiction_button(ack: Ack, body: dict, action: dict, respond: Respond):
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
        "text": "内容について潜在的な矛盾点を指摘してください。",
        "ts": message_ts,
    }
    publish_event(event)


@app.action("google_search_button")
def google_search_button(ack: Ack, body: dict, action: dict, respond: Respond):
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
        "text": "関連する内容をgoogleで検索してください。",
        "ts": message_ts,
    }
    publish_event(event)


@app.action("unresolve_button")
def unresolve_button(ack: Ack, body: dict, action: dict, respond: Respond):
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
        "text": "問題を解決するために足りない文脈があれば箇条書きで教えてください。",
        "ts": message_ts,
    }
    publish_event(event)


@app.action("search_button")
def search_button(ack: Ack, body: dict, action: dict, respond: Respond):
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
        "text": "関連する内容についてSlackを検索して探してください。",
        "ts": message_ts,
    }
    respond(
        "関連する内容についてSlackを検索して回答を生成しています。\n次回からは「slackを検索して〜してください」や「notionを検索して〜してください」のように質問してみてください。",
        replace_original=False,
        thread_ts=thread_ts,
    )
    publish_event(event)


@app.action("notion_button")
def notion_button(ack: Ack, body: dict, action: dict, respond: Respond):
    ack()
    user_id = body["user"]["id"]
    channel_id = body["channel"]["id"]
    thread_ts = body["container"]["thread_ts"]
    message_ts = body["container"]["message_ts"]
    assistant = Assistant(user_id)
    client = assistant.get_client()
    set_user({"id": user_id})
    try:
        thread_messages = get_thread_messages(channel_id, thread_ts)
        if len(thread_messages) == 0:
            return
        message_content = thread_messages[-1].get("text")
        message = "Notionページを作成しています。\nしばらくお待ちください..."
        respond(message)
        # 最初の1kトークンからタイトルを決める
        truncate_message_content = truncate_strings(message_content, max_tokens=1000)
        title = client.generate_title(truncate_message_content)
        slack_url = (
            f"https://slack.com/archives/{channel_id}/p{thread_ts.replace('.', '')}"
        )
        # ファイルタイプがテキストならダウンロードする
        for file in thread_messages[-1].get("files", []):
            if file["mimetype"] != "text/plain":
                continue
            url_private = file["url_private_download"]
            file_data = get_slack_file_bytes(url_private)
            message_content += f"{file_data.decode()}\n"

        # メッセージ内容のNotionページを作成
        result = add_notion_page(title, message_content, slack_url)
        respond(result)
    except Exception as e:
        respond(f"Notionページの作成に失敗しました。{e}")


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
    blocks = []
    blocks.append(Header(text="自動で入力される文脈"))
    for context in [
        "スレッドのメッセージ",
        "チャンネル内のcanvas",
        "アップロードされたファイル",
        "アクションの実行結果",
    ]:
        blocks.append(Section(text=f"• {context}\n"))
    blocks.append(Divider())
    blocks.append(Header(text="アップロード可能なファイル"))
    exts = [f"`{ext}`" for ext in CODE_INTERPRETER_EXTS]
    blocks.append(Section(text=f'• {", ".join(exts)}'))
    blocks.append(Section(text=f"• 任意のチャンネルのcanvas"))
    blocks.append(Section(text=f"• テキストのスニペット"))
    blocks.append(Divider())
    blocks.append(Header(text="アクションの実行ルール"))
    blocks.append(
        Section(
            text="アクションとは、メッセージの内容を検査して特定の条件を満たした場合に実行される処理です。\n"
            "メッセージの内容を検査する `strings` と `condition` の2つの要素で構成されます。"
        )
    )
    blocks.append(Section(text="• strings: メッセージを検査する文字列パターン"))
    blocks.append(Section(text="• condition: メッセージを検査する条件"))
    with open("/function/data/assistant.yml") as f:
        config = yaml.safe_load(f)

    with open("/function/data/assistant.yara") as f:
        parser = plyara.Plyara()
        rules = parser.parse_string(f.read())
        for rule in rules:
            model = config[rule["rule_name"]]
            functions = [
                f'`{tool["function"]["name"]}`'
                for tool in model.get("tools", [])
                if tool["type"] == "function"
            ]
            if len(functions) > 0:
                name = model["name"]
                keywords = []
                for keyword in rule["strings"]:
                    keywords.append(f'`{keyword["value"]}`')
                blocks.append(Header(text=name))
                blocks.append(
                    Section(
                        text=f"アクション: {', '.join(functions)}\nルール:\n```{rule['raw_strings']}\n{rule['raw_condition']}```\n"
                    )
                )
    try:
        payload = Home(blocks=blocks).build()
        # App Home UIの更新
        client.views_publish(user_id=event["user"], view=payload)
    except Exception as e:
        print(f"Error publishing home tab: {e}")


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
