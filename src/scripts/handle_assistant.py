import os
import sys
import time
import json
import logging
import traceback
import sentry_sdk
from slacklib import (
    get_thread_messages,
    add_reaction,
    update_message,
    get_canvas_content,
    delete_message,
    BOT_USER_ID,
)
from ai import (
    run_assistant,
    create_thread,
    update_assistant,
    get_ai_thread_messages,
    create_run,
    create_message,
    update_assistant_tools,
    get_usage,
    HEAVY_MODEL,
    BASE_MODEL,
)
from demo import assistant_instructor, MAX_LEVEL
from datetime import datetime
from tempfile import mkdtemp
from tools import truncate_strings, calculate_token_size
from blockkit import Actions, Button, Divider, Message, Section
from handle_plugin import handle_output_plugin
from langchain_community.callbacks.openai_info import MODEL_COST_PER_1K_TOKENS
from store import get_thread_info, update_thread_info

TEST_USER = os.getenv("TEST_USER")


def truncate_token_size(text, max_tokens):
    origin_token_size = calculate_token_size(text)
    truncated_text = truncate_strings(text, max_tokens)
    token_size = calculate_token_size(truncated_text)
    truncated_token_size = origin_token_size - token_size
    return truncated_text, token_size, truncated_token_size


class ThreadHandler:
    def __init__(self, prompt, files, channel_id):
        self.prompt = prompt
        self.thread_id = None
        self.truncated_token_size = 0
        self.token_size = 0
        self.thread_len = 0
        self.files = files[:]
        self.channel_id = channel_id

    def new_thread(self, thread_messages):
        # canvasがある場合はファイルに書き出してfilesに追加
        canvas_content = get_canvas_content(self.channel_id)
        if len(canvas_content) > 10:
            canvas_file = os.path.join(mkdtemp(), "canvas.md")
            with open(canvas_file, "w") as f:
                f.write(canvas_content)
            self.files.append(canvas_file)
        thread_len = 0
        # 12kトークンに切り捨て
        self.prompt, _token_size, _truncated_token_size = truncate_token_size(
            self.prompt, max_tokens=12000
        )
        self.truncated_token_size = _truncated_token_size
        self.token_size = _token_size
        if len(thread_messages) > 1:
            # スレッド内の全メッセージを取得
            messages = ""
            thread_messages.pop(0)
            for msg in thread_messages:
                # 各メッセージのユーザーIDとテキストを出力
                message_user_id = msg.get("user")
                # Botユーザの発言は無視する
                if message_user_id == BOT_USER_ID:
                    continue
                message_text = msg.get("text")
                if len(message_text) == 0:
                    continue
                messages += f"* <@{message_user_id}>: {message_text}\n"
                thread_len += 1
            # スレッドのメッセージ: 8kトークンに切り捨て
            messages, _token_size, _truncated_token_size = truncate_token_size(
                messages, max_tokens=8000
            )
            self.truncated_token_size += _truncated_token_size
            self.token_size += _token_size
            if len(messages) > 0:
                self.prompt = f"# 指示\n{self.prompt}\n\n# チャット履歴\n{messages}\n"
        self.thread_len = thread_len
        # Thread IDがなければ生成してDynamoDBに格納
        thread = create_thread()
        self.thread_id = thread.id
        logging.info(f"create new thread {self.thread_id}")

    def exists_thread(self, doc, max_tokens=31000):
        # ドキュメントIDが存在する場合はOpenAI Thread IDを取得する
        self.thread_id = doc.get("thread_id")
        self.thread_len = len(get_ai_thread_messages(self.thread_id))
        self.files.extend(doc.get("files", []))

        # 32Kトークンまで切り捨てする
        self.prompt, _token_size, _truncated_token_size = truncate_token_size(
            self.prompt, max_tokens=max_tokens
        )
        self.truncated_token_size = _truncated_token_size
        self.token_size = _token_size
        logging.info(f"exists thread {self.thread_id}")


def handle_assistant(event, process_ts, files, assistant, model):
    user_id = event.get("user")
    message_text = event.get("text", "")
    channel_id = event.get("channel")
    thread_ts = event.get("thread_ts") if "thread_ts" in event else event.get("ts")
    event_ts = event.get("ts")
    file_history = []
    level = assistant.get_level()
    model_name = BASE_MODEL if level < MAX_LEVEL else HEAVY_MODEL
    debug = True if user_id == TEST_USER else False

    prompt = message_text.replace(f"<@{BOT_USER_ID}>", "").strip()
    th = ThreadHandler(prompt, files, channel_id)
    try:
        # DynamoDBからOpenAI Threadを取得
        doc_id = f'{BOT_USER_ID}_run_{thread_ts.replace(".", "")}'
        doc = get_thread_info(doc_id=doc_id)
        if doc is not None:
            model = (
                doc.get("model", model) if not model.get("generated", False) else model
            )
            logging.info(f"load existing model: {model}")
            th.exists_thread(doc)
        else:
            thread_messages = get_thread_messages(channel_id, thread_ts)
            th.new_thread(thread_messages)
        # 過去のファイル履歴からツールを復元する
        file_history.extend(th.files)
        # アシスタントを更新する
        model["tools"] = update_assistant_tools(file_history, tools=model["tools"])
        additional_instructions = model.get("additional_instructions", "")
        logging.info(f"update assistant model: {model}")
        update_assistant(
            assistant.get_assistant_id(),
            model=model_name,
            instructions=model["instructions"],
            tools=model["tools"],
        )
        if not debug:
            try:
                # メッセージを作成する
                create_message(th.thread_id, th.prompt, th.files)
                # Run IDを生成する
                run_id = create_run(
                    th.thread_id,
                    assistant.get_assistant_id(),
                    additional_instructions,
                )
            except Exception as e:
                logging.exception(e)
                # 連続で質問されている場合は失敗するので処理を終了させる
                message = "現在回答を生成中です。しばらく待ってからメッセージを送信してください。"
                update_message(channel_id, process_ts, text=message)
                return
        else:
            run_id = "debug_id"
        # スレッドの状態を更新する
        update_thread_info(
            doc_id=doc_id,
            item={
                "thread_id": th.thread_id,
                "run_id": run_id,
                "model": model,
                "files": file_history,
                "updated_at": int(time.time()),
            },
        )
        # 事前にメッセージを送信
        functions = [
            f"`{tool['function']['name']}`"
            for tool in model["tools"]
            if tool["type"] == "function"
        ]
        cost_1k_token = MODEL_COST_PER_1K_TOKENS.get(model_name, 0.01)
        cost_completion_1k_token = MODEL_COST_PER_1K_TOKENS.get(
            f"{model_name}-completion", 0.03
        )
        total_cost_today = get_usage(datetime.now().strftime("%Y-%m-%d"))
        pre_message = (
            f"`{model_name}`が回答を生成中です。\n"
            "```\n"
            f"会話数: {th.thread_len}, ファイル数: {len(th.files)}\n"
            f"入力トークンの合計: {th.token_size}, 切り捨てられたトークンの合計: {th.truncated_token_size}\n"
            f"予測コスト: {round((th.token_size/1024)*cost_1k_token+(th.token_size/1024)*cost_completion_1k_token, 8)} USD\n"
            f"本日の合計コスト: {total_cost_today} USD\n"
            "```\n"
            f"有効なアクション: {', '.join(functions)}\n"
        )
        if debug:
            pre_message += (
                f"指示:\n```{model['instructions']}```\n"
                f"追加指示:\n```{additional_instructions}```\n"
                f"ツール:\n```{json.dumps(model['tools'], indent=4)}```\n"
            )

        elements = [
            Button(
                action_id="stop_button",
                text=":black_square_for_stop: 停止",
                value="stop",
            )
        ]
        payload = Message(
            blocks=[
                Section(text=pre_message),
                Divider(),
                Actions(elements=elements),
            ]
        ).build()
        res = update_message(channel_id, process_ts, blocks=payload["blocks"])
        if res:
            add_reaction("thinking_face", channel_id, event_ts)

        # Assistant APIを実行
        def callback(completion="no message", files=[]):
            if level < MAX_LEVEL:
                completion = f":beginner: 練習モードで回答しています。\nすべての進捗を達成すると `{HEAVY_MODEL}` が利用できるようになります。\n\n{completion}"
            return handle_output_plugin(channel_id, thread_ts, completion, files)

        def log_callback(log_messages, progress=0):
            markdown_blocks = [Section(text=md) for md in log_messages]
            progress = progress % 10
            progress_bar = (
                ":hourglass_flowing_sand:" * progress if progress > 0 else ":hourglass:"
            )
            payload = Message(
                blocks=[
                    Section(text=pre_message),
                    Divider(),
                    *markdown_blocks,
                    Divider(),
                    Section(text=progress_bar),
                    Divider(),
                    Actions(elements=elements),
                ]
            ).build()
            update_message(
                channel_id,
                process_ts,
                blocks=payload["blocks"],
            )

        total_cost = run_assistant(
            run_id,
            th.thread_id,
            callback=callback,
            log_callback=log_callback,
            model=model_name,
            debug=debug,
        )
        time.sleep(1)
        # ユーザレベルを上げる
        next_level = assistant_instructor(
            channel_id,
            thread_ts,
            user_id,
            model,
            th,
            level,
        )
        assistant.update_level(next_level)
        if not debug:
            delete_message(channel_id, process_ts)
    except Exception as e:
        sentry_sdk.capture_exception(e)
        logging.error(traceback.format_exc())
        handle_output_plugin(channel_id, thread_ts, traceback.format_exc(), files=[])
