import os
import logging
import traceback
import sentry_sdk
from pluginbase import PluginBase
from slacklib import (
    add_reaction,
    update_message,
)

DISABLE_PLUGINS = os.getenv("DISABLE_PLUGINS", "").split(":")

# PluginBase インスタンスを作成
plugin_base = PluginBase(package="plugins")
# 入力されたpromptに対する処理のプラグイン
input_plugin_source = plugin_base.make_plugin_source(searchpath=["./input_plugin"])
# 出力された応答に対する処理のプラグイン
output_plugin_source = plugin_base.make_plugin_source(searchpath=["./output_plugin"])
# ファイルに関するプラグイン
file_plugin_source = plugin_base.make_plugin_source(searchpath=["./file_plugin"])


def handle_output_plugin(completion):
    if len(completion.strip()) == 0:
        return
    files = []
    # プラグインをロードし、関数を呼び出す
    for plugin_name in output_plugin_source.list_plugins():
        if plugin_name in DISABLE_PLUGINS:
            continue
        # プラグインモジュールをインポート
        plugin_module = output_plugin_source.load_plugin(plugin_name)
        try:
            logging.info(f"run extractor {plugin_name}")
            codeblock_files = plugin_module.run(completion)
            logging.info(f"{plugin_name} files: {codeblock_files}")
            if len(codeblock_files) > 0:
                files.extend(codeblock_files)
        except Exception as e:
            sentry_sdk.capture_exception(e)
    return files


def handle_input_plugin(event, process_ts):
    channel_id = event.get("channel")
    event_ts = event.get("ts")
    message_text = event.get("text", "")
    extract_files = []
    additional_prompt = ""
    # プラグインをロードし、関数を呼び出す
    for plugin_name in input_plugin_source.list_plugins():
        # プラグインをロード
        plugin_module = input_plugin_source.load_plugin(plugin_name)
        logging.info(f"run extractor {plugin_name}")
        try:
            prompt, files = plugin_module.run(message_text)
            if len(files) > 0:
                process_message = f"{plugin_name}\n抽出されたファイル数: {len(files)}\n"
                update_message(channel_id, process_ts, process_message)
                extract_files.extend(files)
                additional_prompt += prompt
        except Exception as e:
            sentry_sdk.capture_exception(e)
            logging.exception(e)
            add_reaction("dizzy_face", channel_id, event_ts)
    return additional_prompt, extract_files


def handle_file_plugin(event, files, process_ts):
    user_id = event.get("user")
    channel_id = event.get("channel")
    event_ts = event.get("ts")
    message_text = event.get("text", "")
    response_files = []
    for file_path in files:
        # プラグインとその優先度を格納するリスト
        plugins_with_priority = []
        for plugin_name in file_plugin_source.list_plugins():
            # プラグインの優先度を取得（デフォルトは最低優先度）
            plugin_module = file_plugin_source.load_plugin(plugin_name)
            priority = getattr(plugin_module, "PRIORITY", float("inf"))
            # プラグインとその優先度をリストに追加
            plugins_with_priority.append((priority, plugin_name))
        # 優先度に基づいてプラグインをソート
        plugins_with_priority.sort()

        run_plugin = False
        logging.info(f"load plugins: {plugins_with_priority}")
        # ソートされた順序でプラグインを実行
        for _, plugin_name in plugins_with_priority:
            if plugin_name in DISABLE_PLUGINS:
                continue
            # プラグインモジュールをインポート
            plugin_module = file_plugin_source.load_plugin(plugin_name)
            plugin = plugin_module.CreatePlugin()

            process_files = response_files + [file_path]
            for file in process_files:
                # ファイルの拡張子
                ext = os.path.splitext(file)[1]
                if ext in plugin.target_ext:
                    if not run_plugin:
                        add_reaction("arrows_counterclockwise", channel_id, event_ts)
                    run_plugin = True
                    logging.info(
                        f"run file plugin {plugin_name} ({file}) [{plugin.description}]"
                    )
                    try:
                        update_message(channel_id, process_ts, plugin.description)
                        _response_files, message_text = plugin.run(message_text, file)
                        response_files.extend(_response_files)
                    except Exception as e:
                        sentry_sdk.capture_exception(e)
                        logging.error(traceback.format_exc())
                        add_reaction("dizzy_face", channel_id, event_ts)
        if not run_plugin:
            response_files.append(file_path)
    logging.info(f"[{user_id}] file plugin extract {len(response_files)} files")
    event["text"] = message_text
    return response_files, event
