from slack_sdk import WebClient
import sys, os
from openai import OpenAI
import time

client = WebClient(token=os.getenv("TEST_SLACK_BOT_TOKEN"))
member_id = "U067Z40EWBZ"
channel_id = "C0686VBF9V4"

INTERVAL = 60


def get_assistant():
    assistant_id = os.getenv("TEST_ASSISTANT_ID")
    client = OpenAI()
    assistant = client.beta.assistants.retrieve(assistant_id)
    current_assistant = assistant.model_dump()
    return current_assistant


def post_message_and_get_response(text):
    response = client.chat_postMessage(channel=channel_id, text=text)
    assert response["ok"]
    time.sleep(INTERVAL)
    return get_assistant()


def upload_file_and_get_response(text, file):
    filename = os.path.basename(file)
    response = client.files_upload(
        channels=channel_id, file=file, filename=filename, initial_comment=text
    )
    assert response["ok"]
    time.sleep(INTERVAL)
    return get_assistant()


def assistant_functions(tools):
    functions = [
        tool["function"]["name"] for tool in tools if tool["type"] == "function"
    ]
    return functions


def test_thread_message():
    """2回目のメッセージが正しくツールを追加できるかどうかテストします"""
    text = f"<@{member_id}> test1: ナレッジを検索してください。"
    response = client.chat_postMessage(channel=channel_id, text=text)
    assert response["ok"]
    time.sleep(INTERVAL)
    assistant = get_assistant()
    assert len(assistant["tools"]) == 4
    # 2回目はthread_tsを使う。新しいツールは追加しない
    thread_ts = response["ts"]
    text = f"<@{member_id}> test2: 本日の日付を教えてください。"
    response = client.chat_postMessage(
        channel=channel_id, text=text, thread_ts=thread_ts
    )
    assert response["ok"]
    time.sleep(INTERVAL)
    assistant = get_assistant()
    assert len(assistant["tools"]) == 4
    # ３回目 ツールが追加できるかどうかテスト
    text = f"<@{member_id}> test3: 次のmdファイルを分析してください。"
    file = "sample.md"
    filename = os.path.basename(file)
    response = client.files_upload(
        channels=channel_id,
        thread_ts=thread_ts,
        file=file,
        filename=filename,
        initial_comment=text,
    )
    assert response["ok"]
    time.sleep(INTERVAL)
    assistant = get_assistant()
    assert len(assistant["tools"]) == 5
    # 4回目 ツールが追加できるかどうかテスト
    text = f"<@{member_id}> test4: 次のcsvファイルを分析してください。"
    file = "sample.csv"
    filename = os.path.basename(file)
    response = client.files_upload(
        channels=channel_id,
        thread_ts=thread_ts,
        file=file,
        filename=filename,
        initial_comment=text,
    )
    assert response["ok"]
    time.sleep(INTERVAL)
    assistant = get_assistant()
    assert len(assistant["tools"]) == 6
    # 5回目 ツールが追加できるかどうかテスト
    text = f"<@{member_id}> test5: pythonで実装してください。"
    response = client.chat_postMessage(
        channel=channel_id, thread_ts=thread_ts, text=text
    )
    assert response["ok"]
    time.sleep(INTERVAL)
    assistant = get_assistant()
    assert assistant["tools"] == [{"type": "retrieval"}, {"type": "code_interpreter"}]


def test_multi_assistant():
    assistant = post_message_and_get_response(
        f"<@{member_id}> パブリックデータやパブリックAPIについてナレッジ検索して教えてください。"
    )
    assert len(assistant["tools"]) == 5


def test_check_date_plugin():
    assistant = post_message_and_get_response(
        f"<@{member_id}> 本日の日付を教えてください。"
    )
    assert [] == assistant["tools"]


def test_youtube_plugin():
    assistant = post_message_and_get_response(
        f"<@{member_id}> 以下の内容を要約してください。\nhttps://youtu.be/6JaTWuqRGck?si=a14GxMPXCNEQsrPc"
    )
    assert "open_youtube_url" in assistant_functions(assistant["tools"])


def test_google_search_plugin():
    assistant = post_message_and_get_response(
        f"<@{member_id}> 日本の総理大臣をGoogleで調べてください。"
    )
    assert "google_search" in assistant_functions(assistant["tools"])


def test_notion_plugin():
    assistant = post_message_and_get_response(
        f"<@{member_id}> 以下の内容を要約してください.\nhttps://www.notion.so/9354c68d702342fa9db0f28cdc2a80bd?pvs=4"
    )
    assert "open_notion_url" in assistant_functions(assistant["tools"])


def test_file_csv():
    assistant = upload_file_and_get_response(
        f"<@{member_id}> 次のcsvファイルを分析してください。", "sample.csv"
    )
    assert {"type": "code_interpreter"} in assistant["tools"]
