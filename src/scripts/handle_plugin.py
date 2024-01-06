import os
import logging
import traceback
import sentry_sdk
from slacklib import (
    add_reaction,
    post_message,
    update_message,
)
from store import file_plugin_source, input_plugin_source, output_plugin_source
from blockkit import Actions, Button, Divider, Message, Section

# 無効にするPluginリスt
DISABLE_PLUGINS = os.getenv("DISABLE_PLUGINS", "").split(":")


def handle_output_plugin(channel_id, thread_ts, completion="no message", files=[]):
    if len(completion.strip()) == 0 and len(files) == 0:
        return
    if len(completion.strip()) == 0 and len(files) > 0:
        return post_message(channel_id, thread_ts, files=files)
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
    elements = [
        Button(
            action_id="notion_button",
            text=":memo: Notionページ作成",
            value="notion",
            style="primary",
        ),
        Button(
            action_id="unresolve_button",
            text=":face_with_monocle: 問題が未解決です",
            value="unresolve",
        ),
        Button(
            action_id="contradiction_button",
            text=":face_with_one_eyebrow_raised: 潜在的な問題や矛盾点を探す",
            value="contradiction",
        ),
        Button(
            action_id="search_button",
            text=":slack: 関連する内容を探す",
            value="search",
        ),
        Button(
            action_id="google_search_button",
            text=":mag: googleで検索",
            value="google_search",
        ),
    ]
    payload = Message(
        blocks=[
            Section(text=completion),
            Divider(),
            Actions(elements=elements),
        ]
    ).build()
    return post_message(channel_id, thread_ts, blocks=payload["blocks"], files=files)


def handle_input_plugin(event, process_ts):
    upload_files = []
    channel_id = event.get("channel")
    event_ts = event.get("ts")
    user_id = event.get("user")
    # プラグインとその優先度を格納するリスト
    plugins_with_priority = []
    for plugin_name in input_plugin_source.list_plugins():
        if plugin_name in DISABLE_PLUGINS:
            continue
        # プラグインの優先度を取得（デフォルトは最低優先度）
        plugin_module = input_plugin_source.load_plugin(plugin_name)
        priority = getattr(plugin_module, "PRIORITY", float("inf"))
        # プラグインとその優先度をリストに追加
        plugins_with_priority.append((priority, plugin_name))
    # 優先度に基づいてプラグインをソート
    plugins_with_priority.sort()
    # ソートされた順序でプラグインを実行
    for _, plugin_name in plugins_with_priority:
        # プラグインをロード
        plugin_module = input_plugin_source.load_plugin(plugin_name)
        logging.info(f"run extractor {plugin_name} {plugin_module.DESCRIPTION}")
        try:
            _event, files, processed = plugin_module.run(event)
            if type(_event) == dict:
                event = _event
            else:
                logging.error(f"invalid event type: {type(_event)}")
            if processed:
                process_message = (
                    f"{plugin_module.DESCRIPTION}\n抽出されたファイル数: {len(files)}\n"
                )
                update_message(channel_id, process_ts, process_message)
            if len(files) > 0:
                upload_files.extend(files)
        except Exception as e:
            logging.info(event)
            sentry_sdk.capture_exception(e)
            logging.error(traceback.format_exc())
            add_reaction("dizzy_face", channel_id, event_ts)
    logging.info(f"[{user_id}] input plugin extract {len(upload_files)} files")
    logging.info(upload_files)
    return upload_files, event


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
