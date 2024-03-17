import os
import json
import time
import yara
import yaml
import logging
import requests
import sentry_sdk
from openai import OpenAI
from tempfile import mkdtemp
from typing_extensions import override
from openai import AssistantEventHandler
from openai.types.beta import AssistantStreamEvent
from openai.types.beta.threads import Text, TextDelta
from openai.types.beta.threads.runs import RunStep, RunStepDelta
from langchain_community.chat_models import ChatOpenAI
from langchain.schema import HumanMessage, SystemMessage
from tools import browser_open
from slacklib import BOT_USER_ID
from langchain_community.callbacks.openai_info import get_openai_token_cost_for_model

from tools import *

BASE_MODEL = os.getenv("BASE_MODEL", "gpt-3.5-turbo-0125")
HEAVY_MODEL = os.getenv("HEAVY_MODEL", "gpt-4-turbo-preview")


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


# ツール呼び出しの結果を処理し、必要なアクションがある場合はそれを実行します。
def tool_call_handler(run, client, message_callback, step_callback):
    if (
        not hasattr(run, "required_action")
        or not hasattr(run.required_action, "submit_tool_outputs")
        or run.required_action.type != "submit_tool_outputs"
    ):
        return
    tool_outputs = []
    for tool_call in run.required_action.submit_tool_outputs.tool_calls:
        tool_id = tool_call.id
        result = step_callback.function_call(
            tool_call.function.name, tool_call.function.arguments
        )
        tool_outputs.append(
            {
                "tool_call_id": tool_id,
                "output": result,
            }
        )
    with client.beta.threads.runs.submit_tool_outputs_stream(
        thread_id=run.thread_id,
        run_id=run.id,
        tool_outputs=tool_outputs,
        event_handler=SlackAssistantEventHandler(
            client, message_callback, step_callback
        ),
    ) as stream:
        stream.until_done()


# イベントハンドラーのクラスです。OpenAI Assistantからのイベントを処理します。
class SlackAssistantEventHandler(AssistantEventHandler):
    def __init__(self, client, message_callback, step_callback) -> None:
        super().__init__()
        self.message_callback = message_callback
        self.step_callback = step_callback
        self.client = client

    # ファイルを取得し、指定されたディレクトリに保存します。
    def retrieve_file(self, file_id, ext=None, directory="/tmp"):
        file = self.client.files.retrieve(file_id)
        filename = os.path.basename(file.filename)
        if ext is not None:
            filename = f"{filename}.{ext}"
        path = os.path.join(directory, filename)
        content = self.client.files.content(file_id)
        with open(path, "wb") as f:
            f.write(content.read())
        return path

    # テキストの変更を処理します。
    @override
    def on_text_delta(self, delta: TextDelta, snapshot: Text) -> None:
        if len(snapshot.value) != 0:
            self.message_callback.update(delta.value)

    # テキストの処理が完了したときの処理を行います。
    @override
    def on_text_done(self, text) -> None:
        # テキスト内の注釈を処理します
        for annotation in text.annotations:
            # ファイルパス注釈を処理します
            if annotation.type == "file_path":
                file_id = annotation.file_path.file_id
                annotation_file = self.retrieve_file(file_id)
                self.message_callback.set_files([annotation_file])
        self.message_callback.done(text.value)

    # 実行ステップの変更を処理します。
    @override
    def on_run_step_delta(self, delta: RunStepDelta, snapshot: RunStep) -> None:
        details = delta.step_details
        if details is not None and details.type == "tool_calls":
            for tool in details.tool_calls or []:
                if (
                    tool.type == "code_interpreter"
                    and tool.code_interpreter
                    and tool.code_interpreter.input
                ):
                    if len(tool.code_interpreter.input) != 0:
                        self.step_callback.update(tool.code_interpreter.input)
                if (
                    tool.type == "code_interpreter"
                    and tool.code_interpreter
                    and tool.code_interpreter.outputs
                ):
                    for output in tool.code_interpreter.outputs:
                        if hasattr(output, "logs"):
                            self.step_callback.set_output(output.logs)
                        if hasattr(output, "image"):
                            file_id = output.image.file_id
                            path = self.retrieve_file(file_id, "png")
                            self.message_callback.set_files([path])

    # 実行ステップが完了したときの処理を行います。
    @override
    def on_run_step_done(self, run_step: RunStep) -> None:
        details = run_step.step_details
        if details.type == "tool_calls":
            for tool in details.tool_calls:
                if tool.type == "code_interpreter":
                    self.step_callback.done()

    # ツール呼び出しが完了したときの処理を行います。
    @override
    def on_tool_call_done(self, tool_call) -> None:
        if tool_call.type == "function":
            run = self.current_run
            tool_call_handler(
                run,
                self.client,
                self.message_callback,
                self.step_callback,
            )

    # タイムアウト時の処理を行います。
    @override
    def on_timeout(self):
        self.message_callback.create()
        self.message_callback.done(f"タイムアウトしました")

    # 例外が発生したときの処理を行います。
    @override
    def on_exception(self, exception: Exception) -> None:
        self.message_callback.update(f"Error: {exception}")

    # イベントが発生したときの処理を行います。
    @override
    def on_event(self, event: AssistantStreamEvent) -> None:
        if event.event == "thread.run.completed":
            self.message_callback.end()

        if event.event == "thread.run.failed":
            self.message_callback.update(event.data.last_error.message)

        if event.event == "thread.run.created":
            from store import update_run_id

            thread_ts = self.message_callback.message_ts
            doc_id = f'{BOT_USER_ID}_run_{thread_ts.replace(".", "")}'
            run_id = event.data.id
            update_run_id(doc_id, run_id)


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


class AssistantAPIClient:
    def __init__(self, api_key) -> None:
        self.api_key = api_key
        self.client = OpenAI(timeout=20.0, max_retries=3, api_key=self.api_key)

    def create_thread(self):
        return self.client.beta.threads.create()

    def get_ai_thread_messages(self, thread_id):
        return list(
            self.client.beta.threads.messages.list(thread_id=thread_id, order="desc")
        )

    def create_assistant(self, name, instructions=""):
        assistant = self.client.beta.assistants.create(
            name=name,
            instructions=instructions,
            tools=[{"type": "retrieval"}],
            model=BASE_MODEL,
        )
        return assistant.id

    def get_assistant_filenames(self, assistant_id):
        filenames = []
        try:
            for file_id in self.client.beta.assistants.retrieve(assistant_id).file_ids:
                filename = self.client.files.retrieve(file_id).filename
                filenames.append(filename)
        except Exception as e:
            logging.exception(e)
        return filenames

    def delete_assistant_files(self, assistant_id):
        try:
            assistant = self.client.beta.assistants.retrieve(assistant_id)
            current_assistant = assistant.model_dump()
            file_ids = current_assistant["file_ids"]
            self.client.beta.assistants.update(assistant_id, file_ids=[], tools=[])
            for file_id in file_ids:
                logging.info(f"delete {file_id}")
                self.client.files.delete(file_id)
        except Exception as e:
            logging.exception(e)
            return False
        return True

    def update_assistant_tools(self, files, tools=[]):
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

    def update_knowledge_files(self, knowledge_files, file_ids=[]):
        for knowledge_file in knowledge_files:
            logging.info(f"update knowledge: {knowledge_file}")
            file = self.client.files.create(
                file=open(knowledge_file, "rb"), purpose="assistants"
            )
            logging.info(f"add knowledge file: {knowledge_file} -> {file.id}")
            file_ids.append(file.id)
        return file_ids

    def get_assistant(self, assistant_id):
        assistant = self.client.beta.assistants.retrieve(assistant_id)
        current_assistant = assistant.model_dump()
        return current_assistant

    def update_assistant(
        self,
        assistant_id,
        knowledge_files=[],
        instructions=None,
        model=BASE_MODEL,
        tools=None,
    ):
        current_assistant = self.get_assistant(assistant_id)
        logging.info(f"current_assistant: {current_assistant}")
        file_ids = current_assistant["file_ids"]
        # Assistantを初期化しない場合はツールを追記する
        # 既存のツールの構成を更新する
        new_tools = tools if tools is not None else current_assistant["tools"]

        new_instructions = (
            current_assistant["instructions"] if instructions is None else instructions
        )

        file_ids = self.update_knowledge_files(knowledge_files, file_ids)

        logging.info(f"update tools: {new_tools}")

        new_assistant = self.client.beta.assistants.update(
            assistant_id,
            file_ids=file_ids,
            instructions=new_instructions,
            model=model,
            tools=new_tools,
        )
        filenames = []
        for file_id in new_assistant.file_ids:
            filename = self.client.files.retrieve(file_id).filename
            filenames.append(filename)

        return filenames

    def create_message(self, thread_id, content, files=[], role="user"):
        file_ids = []
        for file in files:
            file = self.client.files.create(file=open(file, "rb"), purpose="assistants")
            file_ids.append(file.id)
        return self.client.beta.threads.messages.create(
            thread_id=thread_id, role=role, content=content, file_ids=file_ids
        )

    def cancel_run(self, thread_id, run_id):
        logging.info(f"cancel {run_id}:{thread_id}")
        return self.client.beta.threads.runs.cancel(thread_id=thread_id, run_id=run_id)

    def run_assistant(
        self, th, assistant, message_callback, step_callback, additional_instructions
    ):
        try:

            assistant_id = assistant.get_assistant_id()
            with self.client.beta.threads.runs.create_and_stream(
                thread_id=th.thread_id,
                assistant_id=assistant_id,
                event_handler=SlackAssistantEventHandler(
                    self.client, message_callback, step_callback
                ),
            ) as stream:
                stream.until_done()
        except Exception as e:
            logging.exception(e)

    def get_usage(self, date):
        url = "https://api.openai.com/v1/usage"
        headers = {"Authorization": f"Bearer {self.api_key}"}
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
