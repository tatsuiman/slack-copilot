import os
import json
import time
import yara
import yaml
import logging
import requests
import sentry_sdk
from slacklib import upload_file
from openai import OpenAI
from tempfile import mkdtemp
from pluginbase import PluginBase
from langchain_community.chat_models import ChatOpenAI
from langchain.schema import HumanMessage, SystemMessage
from langchain.agents.openai_assistant import OpenAIAssistantRunnable
from tools import truncate_strings, calculate_token_size, browser_open
from langchain_community.callbacks.openai_info import (
    MODEL_COST_PER_1K_TOKENS,
    get_openai_token_cost_for_model,
)

# PluginBase インスタンスを作成
plugin_base = PluginBase(package="plugins")
# プラグインのソースを作成（プラグインが置かれるディレクトリを指定）
function_source = plugin_base.make_plugin_source(searchpath=["./functions"])

from tools import *

BASE_MODEL = os.getenv("BASE_MODEL", "gpt-3.5-turbo-0125")
HEAVY_MODEL = os.getenv("HEAVY_MODEL", "gpt-4-turbo-preview")

client = OpenAI(timeout=20.0, max_retries=3)

# https://platform.openai.com/docs/assistants/tools/supported-files
RETRIEVAL_EXTS = (
    ".c",  # text/x-c
    ".cpp",  # text/x-c++
    ".docx",  # application/vnd.openxmlformats-officedocument.wordprocessingml.document
    ".html",  # text/html
    ".java",  # text/x-java
    ".json",  # application/json
    ".md",  # text/markdown
    ".pdf",  # application/pdf
    ".php",  # text/x-php
    ".pptx",  # application/vnd.openxmlformats-officedocument.presentationml.presentation
    ".py",  # text/x-python
    ".py",  # text/x-script.python
    ".rb",  # text/x-ruby
    ".tex",  # text/x-tex
    ".txt",  # text/plain
)

CODE_INTERPRETER_EXTS = (
    ".csv",
    ".xlsx",
    ".tar",
    ".js",
    ".css",
    ".xml",
) + RETRIEVAL_EXTS

BUCKET_NAME = os.getenv("GCS_BUCKET_NAME")


def generate_assistant_model(event):
    assistant_file = "/function/data/assistant.yml"
    yara_file = "/function/data/assistant.yara"
    message_rules = yara.compile(filepath=yara_file)
    # メッセージを取得
    message = event["text"]
    # メッセージにマッチするルールを検索
    matches = message_rules.match(data=message)
    # モデルを初期化
    model = {
        "tools": [],
        "files": [],
        "instructions": "あなたはユーザに質問に回答するアシスタントです",
        "additional_instructions": "",
    }
    # マッチしたルールがある場合
    if matches:
        # アシスタントファイルを開き、データを読み込む
        with open(assistant_file, "r") as f:
            assistant_data = yaml.safe_load(f)
        # 各マッチに対して
        for match in matches:
            # マッチしたルールがアシスタントデータに存在する場合
            if match.rule in assistant_data:
                logging.info(f"match yara rule: {match.rule}")
                assistant = assistant_data[match.rule]
                instructions = assistant.get("instructions")
                additional_instructions = assistant.get("additional_instructions")
                model["generated"] = True
                model["tools"].extend(assistant.get("tools", []))
                model["instructions"] = model.get("instructions", instructions)
                if additional_instructions is not None:
                    model["additional_instructions"] += additional_instructions
                # ファイルを処理
                for file in assistant.get("files", []):
                    filename = f"/function/data/{file}"
                    if os.path.exists(filename):
                        model["files"].append(filename)
                # URLを処理
                for u in assistant.get("urls", []):
                    url = u["url"]
                    file = u["file"]
                    title, content = browser_open(url)
                    filename = os.path.join(mkdtemp(), file)
                    with open(filename, "w") as f:
                        f.write(content)
                    model["files"].append(filename)
        # モデルを返す
        return model
    # マッチしたルールがない場合、Noneを返す
    return


def create_thread():
    return client.beta.threads.create()


def get_ai_thread_messages(thread_id):
    return list(client.beta.threads.messages.list(thread_id=thread_id, order="desc"))


def create_assistant(name, instructions=""):
    interpreter_assistant = OpenAIAssistantRunnable.create_assistant(
        name=name,
        instructions=instructions,
        tools=[{"type": "retrieval"}],
        model=BASE_MODEL,
    )
    return interpreter_assistant.assistant_id


def get_assistant_filenames(assistant_id):
    filenames = []
    try:
        for file_id in client.beta.assistants.retrieve(assistant_id).file_ids:
            filename = client.files.retrieve(file_id).filename
            filenames.append(filename)
    except Exception as e:
        logging.exception(e)
    return filenames


def delete_assistant_files(assistant_id):
    try:
        assistant = client.beta.assistants.retrieve(assistant_id)
        current_assistant = assistant.model_dump()
        file_ids = current_assistant["file_ids"]
        client.beta.assistants.update(assistant_id, file_ids=[], tools=[])
        for file_id in file_ids:
            logging.info(f"delete {file_id}")
            client.files.delete(file_id)
    except Exception as e:
        logging.exception(e)
        return False
    return True


def update_assistant_tools(files, tools=[]):
    for knowledge_file in files:
        if (
            knowledge_file.endswith(RETRIEVAL_EXTS)
            and {"type": "retrieval"} not in tools
        ):
            tools.append({"type": "retrieval"})

        if (
            not knowledge_file.endswith(RETRIEVAL_EXTS)
            and {"type": "code_interpreter"} not in tools
        ):
            tools.append({"type": "code_interpreter"})
    return tools


def update_knowledge_files(knowledge_files, file_ids=[]):
    for knowledge_file in knowledge_files:
        logging.info(f"update knowledge: {knowledge_file}")
        file = client.files.create(
            file=open(knowledge_file, "rb"), purpose="assistants"
        )
        logging.info(f"add knowledge file: {knowledge_file} -> {file.id}")
        file_ids.append(file.id)
    return file_ids


def get_assistant(assistant_id):
    assistant = client.beta.assistants.retrieve(assistant_id)
    current_assistant = assistant.model_dump()
    return current_assistant


def update_assistant(
    assistant_id,
    knowledge_files=[],
    instructions=None,
    model=BASE_MODEL,
    tools=None,
):
    current_assistant = get_assistant(assistant_id)
    logging.info(f"current_assistant: {current_assistant}")
    file_ids = current_assistant["file_ids"]
    # Assistantを初期化しない場合はツールを追記する
    # 既存のツールの構成を更新する
    new_tools = tools if tools is not None else current_assistant["tools"]

    new_instructions = (
        current_assistant["instructions"] if instructions is None else instructions
    )

    file_ids = update_knowledge_files(knowledge_files, file_ids)

    logging.info(f"update tools: {new_tools}")

    new_assistant = client.beta.assistants.update(
        assistant_id,
        file_ids=file_ids,
        instructions=new_instructions,
        model=model,
        tools=new_tools,
    )
    filenames = []
    for file_id in new_assistant.file_ids:
        filename = client.files.retrieve(file_id).filename
        filenames.append(filename)

    return filenames


def create_run(thread_id, assistant_id, additional_instructions=None):
    return client.beta.threads.runs.create(
        thread_id=thread_id,
        assistant_id=assistant_id,
        additional_instructions=additional_instructions,
    ).id


def create_message(thread_id, content, files=[], role="user"):
    file_ids = []
    for file in files:
        file = client.files.create(file=open(file, "rb"), purpose="assistants")
        file_ids.append(file.id)
    return client.beta.threads.messages.create(
        thread_id=thread_id, role=role, content=content, file_ids=file_ids
    )


def cancel_run(thread_id, run_id):
    logging.info(f"cancel {run_id}:{thread_id}")
    return client.beta.threads.runs.cancel(thread_id=thread_id, run_id=run_id)


def run_assistant(
    run_id,
    thread_id,
    callback,
    log_callback,
    timeout=300,
    max_messages=20,
    model=BASE_MODEL,
    debug=False,
):
    log_messages = []
    messages = client.beta.threads.messages.list(thread_id=thread_id, order="desc")
    current_message_len = len(list(messages)) + 1
    ignore_ids = []
    progress = 0
    if max_messages < current_message_len:
        message = f"メッセージ数の上限({max_messages})に達しました"
        logging.error(message)
        log_messages.append(message)
        log_callback(log_messages, progress)
        return

    if debug:
        message = f"```thread_id: {thread_id}\nrun_id: {run_id}\nmessage: {current_message_len}```"
        log_messages.append("デバッグ中です。")
        for i in range(1, 5):
            log_callback(log_messages, progress=i)
            time.sleep(1)
        callback(message)
        return

    logging.info(f"start assistant run {run_id}:{thread_id}")
    for i in range(timeout):
        run = client.beta.threads.runs.retrieve(thread_id=thread_id, run_id=run_id)
        messages = client.beta.threads.messages.list(thread_id=thread_id, order="desc")
        # 進捗を計算
        progress += 1
        log_callback(log_messages, progress)

        if run.status == "requires_action":
            tool_outputs = []
            for tool_call in run.required_action.submit_tool_outputs.tool_calls:
                tool_id = tool_call.id
                function_name = tool_call.function.name
                function_arguments = json.loads(tool_call.function.arguments)
                call_message = f"call: {function_name}({function_arguments})"
                logging.info(call_message)
                log_messages.append(
                    f"`{function_name}`を実行しています(`{function_arguments}`)"
                )
                log_callback(log_messages, progress)
                result = process_function_call(function_name, function_arguments)
                logging.info(f"tool_id: {tool_id} result: {len(result)}")
                # 結果を保存
                tool_outputs.append(
                    {
                        "tool_call_id": tool_id,
                        "output": result,
                    }
                )
                output_token = calculate_token_size(result)
                log_messages.append(
                    f"`{function_name}`を実行しました。結果のトークン数: {output_token}"
                )
                log_callback(log_messages, progress)
            run = client.beta.threads.runs.submit_tool_outputs(
                thread_id=thread_id,
                run_id=run.id,
                tool_outputs=tool_outputs,
            )

        if run.status == "in_progress":
            resp = client.beta.threads.runs.steps.list(
                thread_id=thread_id,
                run_id=run.id,
            )

            if len(list(resp)) > 0:
                run_steps = list(reversed(list(resp)))
                for step in run_steps:
                    ignore_ids = process_step(step, callback, ignore_ids)

            if current_message_len < len(list(messages)):
                current_message_len = len(list(messages))
                process_message(messages, callback)

        if run.status == "completed":
            logging.info("compleated")
            process_message(messages, callback)
            usage = run.usage
            const_1k_token = MODEL_COST_PER_1K_TOKENS.get(model, 0.01)
            const_completion_1k_token = MODEL_COST_PER_1K_TOKENS.get(
                f"{model}-completion", 0.03
            )
            total_cost = round(
                (usage.prompt_tokens / 1024) * const_1k_token
                + (usage.completion_tokens / 1024) * const_completion_1k_token,
                8,
            )
            return total_cost

        if run.status == "failed":
            message = f":fire: 応答に失敗しました {run.last_error.message}"
            logging.exception(message)
            log_messages.append(message)
            log_callback(log_messages, progress)
            return

        if run.status in ["cancelling", "cancelled"]:
            message = f"出力をキャンセルしました。"
            logging.exception(message)
            log_messages.append(message)
            log_callback(log_messages, progress)
            return

        time.sleep(1)
    return "アシスタントの応答がタイムアウトしました。"


def process_function_call(function_name, function_arguments):
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
                plugin_result = plugin_module.run(**function_arguments)
                # 8kになるように切り捨てする
                result = truncate_strings(plugin_result, max_tokens=16000)
            except Exception as e:
                sentry_sdk.capture_exception(e)
                logging.exception(e)
            break
    if len(result) == 0:
        result = "no result"
    return result


def process_step(step, callback, ignore_ids=[]):
    for step_type, step_details in step.step_details:
        if step_type != "tool_calls":
            continue
        if step.id in ignore_ids:
            continue
        for detail in step_details:
            if type(detail) != dict:
                detail = detail.model_dump()
            if detail["type"] == "function":
                output = detail["function"].get("output")
                if output:
                    ignore_ids.append(step.id)
            if detail["type"] == "code_interpreter":
                code = detail["code_interpreter"]["input"]
                if len(code) > 0:
                    code_message = f"以下のコードを実行します\n```\n{code}\n```\n"
                    outputs = detail["code_interpreter"]["outputs"]
                    for output in outputs:
                        code_message += (
                            f"実行結果\n```\n{output.get('logs') or output}\n```\n"
                        )
                    if len(outputs) > 0:
                        callback(code_message)
                        ignore_ids.append(step.id)
    return ignore_ids


def process_message(messages, callback):
    res = {}
    for message in messages:
        files = []
        message_text = "files"
        if message.role == "assistant":
            citations = set()
            citation_links = {}
            # メッセージの内容を処理します
            for message_content in message.content:
                # テキストタイプのメッセージを処理します
                if message_content.type == "text":
                    message_text = message_content.text.value
                    # テキスト内の注釈を処理します
                    for annotation in message_content.text.annotations:
                        # ファイルパス注釈を処理します
                        if annotation.type == "file_path":
                            file_id = annotation.file_path.file_id
                            annotation_file = retrieve_file(file_id, directory="/tmp")
                            files.append(annotation_file)

                        # ファイル引用注釈を処理します
                        if file_citation := getattr(annotation, "file_citation", None):
                            cited_file = client.files.retrieve(file_citation.file_id)
                            citation = f"{cited_file.filename}{annotation.text}"
                            # 新しい引用を処理します
                            if not citation in citations:
                                citations.add(citation)
                                citation_file = os.path.join(
                                    mkdtemp(), cited_file.filename
                                )
                                with open(citation_file, "w") as f:
                                    f.write(file_citation.quote)
                                permalink = upload_file(
                                    citation_file, cited_file.filename
                                )
                                citation_links[citation] = permalink
                            else:
                                permalink = citation_links[citation]
                            # メッセージテキスト内の引用をリンクに置き換えます
                            message_text = message_text.replace(
                                annotation.text,
                                f"[<{permalink}|{cited_file.filename}>]",
                            )
                if message_content.type == "image_file":
                    file_id = message_content.image_file.file_id
                    png_file = retrieve_file(file_id, directory="/tmp")
                    logging.info(f"download file: {file_id} ({png_file})")
                    files.append(png_file)
            res = callback(message_text, files=files)
            break
    return res


def retrieve_file(file_id, directory="/tmp"):
    file = client.files.retrieve(file_id)
    filename = os.path.basename(file.filename)
    ext = os.path.splitext(filename)[1]
    if not ext:
        filename = f"{filename}.png"
    path = os.path.join(directory, filename)
    content = client.files.content(file_id)
    content.stream_to_file(path)
    return path


def generate_json(text, system_prompt, key_name):
    chat = ChatOpenAI(model=BASE_MODEL).bind(response_format={"type": "json_object"})
    output = chat.invoke(
        [
            SystemMessage(content=system_prompt),
            HumanMessage(content=text),
        ]
    )
    title = json.loads(output.content)[key_name]
    return title


def generate_title(text):
    system_prompt = 'あたえられた文字列からタイトルを考えて次のjsonフォーマットで出力してください。\n```{"title": "こちらにタイトルを入れてください"}```'
    return generate_json(text, system_prompt, "title")


def get_usage(date):
    url = "https://api.openai.com/v1/usage"
    headers = {"Authorization": f"Bearer {os.environ.get('OPENAI_API_KEY')}"}
    params = {"date": date}
    total_cost = 0
    try:
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        response = response.json()
        usage_data = response["data"]
        for record in usage_data:
            model = record["snapshot_id"]
            try:
                cost_per_completion_token = get_openai_token_cost_for_model(
                    model,
                    num_tokens=record["n_generated_tokens_total"],
                    is_completion=True,
                )
                cost_per_token = get_openai_token_cost_for_model(
                    model,
                    num_tokens=record["n_context_tokens_total"],
                    is_completion=False,
                )
            except Exception as e:
                cost_per_completion_token = 0.03
                cost_per_token = 0.01
            total_cost += (
                cost_per_token + cost_per_completion_token
            )  # トータルコストの計算
    except Exception as e:
        print(f"OpenAI APIのレスポンス処理中にエラーが発生しました: {e}")

    return total_cost
