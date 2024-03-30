import os
import sys
import time
import json
import logging
import sentry_sdk
from pluginbase import PluginBase
from slacklib import post_message
from plugin import handle_output_plugin
from slacklib import post_message, update_message, upload_file
from ui import generate_step_block
from tools import truncate_strings, calculate_token_size

STREAM_RATE = 1
SLACK_MAX_TOKEN_SIZE = 1500

# PluginBase インスタンスを作成
plugin_base = PluginBase(package="plugins")
# プラグインのソースを作成（プラグインが置かれるディレクトリを指定）
function_source = plugin_base.make_plugin_source(searchpath=["./functions"])


# Slackへのメッセージコールバックを処理するクラスです。
class MessageCallback:
    def __init__(self, channel_id, message_ts) -> None:
        self.count = 0
        self.message = ""
        self.channel_id = channel_id
        self.message_ts = message_ts
        self.ts = 0
        self.last_update_time = 0
        self.current_message = ""

    # メッセージの作成を行います。
    def create(self) -> None:
        res = post_message(self.channel_id, self.message_ts, "Message Typing...")
        self.ts = res["ts"]

    # ファイルを設定します。
    def set_files(self, files):
        message = ""
        for file in files:
            filename = os.path.basename(file)
            permalink = upload_file(file, filename)
            message += f"<{permalink}|{filename}>\n"
        post_message(self.channel_id, self.message_ts, message)

    # メッセージを更新します。
    def update(self, message: str) -> None:
        current_time = time.time()
        output_token = calculate_token_size(self.current_message + message)
        if output_token > SLACK_MAX_TOKEN_SIZE or self.ts == 0:
            if output_token > SLACK_MAX_TOKEN_SIZE:
                update_message(self.channel_id, self.ts, self.current_message)
            self.create()
            self.current_message = message
        else:
            self.current_message += message

        if current_time - self.last_update_time >= STREAM_RATE:
            update_message(self.channel_id, self.ts, self.current_message)
            self.last_update_time = current_time

    # メッセージの処理が完了したときの処理を行います。
    def done(self, message):
        files = handle_output_plugin(message)
        self.set_files(files)
        update_message(self.channel_id, self.ts, self.current_message)
        self.ts = 0

    # メッセージの終了処理を行います。
    def end(self):
        pass


# ステップコールバックを処理するクラスです。
class StepCallback:
    def __init__(self, channel_id, message_ts) -> None:
        self.output = "none"
        self.channel_id = channel_id
        self.message_ts = message_ts
        self.ts = 0
        self.last_update_time = 0
        self.current_message = ""

    # コード入力の開始を通知します。
    def create(self) -> None:
        res = post_message(self.channel_id, self.message_ts, "Code Typing...")
        self.ts = res["ts"]

    # コードメッセージを更新します。
    def _update_code_message(self, message):
        message = f"コード\n```\n{message}\n```\n"
        update_message(self.channel_id, self.ts, message)

    # メッセージを更新します。
    def update(self, message: str) -> None:
        current_time = time.time()
        output_token = calculate_token_size(self.current_message + message)
        if output_token > SLACK_MAX_TOKEN_SIZE or self.ts == 0:
            if output_token > SLACK_MAX_TOKEN_SIZE:
                self._update_code_message(self.current_message)
            self.create()
            self.current_message = message
        else:
            self.current_message += message

        if current_time - self.last_update_time >= STREAM_RATE:
            self._update_code_message(self.current_message)
            self.last_update_time = current_time

    # 関数呼び出しを行います。
    def function_call(self, function_name, arguments) -> None:
        self.create()
        argument = json.loads(arguments)
        argument_truncated = truncate_strings(arguments, max_tokens=20)
        message = f"call: `{function_name}({argument_truncated})`\n"
        update_message(self.channel_id, self.ts, message)

        # プラグインとその優先度を格納するリスト
        plugins_with_priority = []
        for plugin_name in function_source.list_plugins():
            # プラグインの優先度を取得（デフォルトは最低優先度）
            plugin_module = function_source.load_plugin(plugin_name)
            priority = getattr(plugin_module, "PRIORITY", float("inf"))
            # プラグインとその優先度をリストに追加
            plugins_with_priority.append((priority, plugin_name))
        result = ""
        # 優先度に基づいてプラグインをソート
        plugins_with_priority.sort()
        # ソートされた順序でプラグインを実行
        for _, plugin_name in plugins_with_priority:
            # プラグインをロード
            plugin_module = function_source.load_plugin(plugin_name)
            if function_name == plugin_name:
                try:
                    logging.info(f"run extractor {plugin_name}")
                    # プラグインモジュールから関数を呼び出す
                    plugin_result = plugin_module.run(**argument)
                    # 8kになるように切り捨てする
                    result = truncate_strings(plugin_result, max_tokens=16000)
                except Exception as e:
                    sentry_sdk.capture_exception(e)
                    logging.exception(e)
                break
        if len(result) == 0:
            result = "no result"
        output_token = calculate_token_size(result)
        message += (
            f"`{function_name}`を実行しました。結果のトークン数: {output_token}\n"
        )
        update_message(self.channel_id, self.ts, message)
        return result

    # 出力を設定します。
    def set_output(self, output: str) -> None:
        self.output = output

    # 処理が完了したときの処理を行います。
    def done(self):
        message = f"コード\n```\n{self.current_message}\n```\n実行結果\n```\n{self.output}\n```\n"
        truncated_message = truncate_strings(message, max_tokens=2500)
        blocks = generate_step_block(truncated_message)
        update_message(self.channel_id, self.ts, blocks=blocks)
        self.ts = 0
        self.output = "none"
