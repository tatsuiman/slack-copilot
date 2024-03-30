import os
from openai import OpenAI
from pinecone import Pinecone
from typing_extensions import override
from openai import AssistantEventHandler, OpenAI
from openai.types.beta.threads import Text, TextDelta
from openai.types.beta.threads.runs import ToolCall, ToolCallDelta


class EventHandler(AssistantEventHandler):
    @override
    def on_text_created(self, text: Text) -> None:
        print(f"\nassistant > ", end="", flush=True)

    @override
    def on_text_delta(self, delta: TextDelta, snapshot: Text):
        print(delta.value, end="", flush=True)

    def on_tool_call_created(self, tool_call: ToolCall):
        print(f"\nassistant > {tool_call.type}\n", flush=True)

    def on_tool_call_delta(self, delta: ToolCallDelta, snapshot: ToolCall):
        if delta.type == "code_interpreter":
            if delta.code_interpreter.input:
                print(delta.code_interpreter.input, end="", flush=True)
            if delta.code_interpreter.outputs:
                print(f"\n\noutput >", flush=True)
                for output in delta.code_interpreter.outputs:
                    if output.type == "logs":
                        print(f"\n{output.logs}", flush=True)


pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
client = OpenAI()

index_name = "semantic-search-openai"
embedding_model = "text-embedding-3-small"

# 質問内容
query = "ChatGPTがユーザーの好みや情報を取得することはできますか？"
# 質問内容をベクトル化
xq = client.embeddings.create(input=query, model=embedding_model).data[0].embedding
index = pc.Index(index_name)

# 質問内容に関連した上位３件の類似した内容のスレッドを検索します
res = index.query(vector=[xq], top_k=3, include_metadata=True)
for match in res["matches"]:
    # 閾値以上のスレッドを割り当てて回答する
    if match["score"] > 0.5:
        thread_id = match["id"]
        try:
            # アシスタントを作成する
            assistant = client.beta.assistants.create(
                name="Test Assistant",
                tools=[{"type": "code_interpreter"}],
                model="gpt-4-1106-preview",
            )
            # 取得したスレッドにメッセージを追加
            client.beta.threads.messages.create(
                thread_id=thread_id,
                role="user",
                content=query,
            )
            # runオブジェクトを生成して回答を生成する
            with client.beta.threads.runs.create_and_stream(
                thread_id=thread_id,
                assistant_id=assistant.id,
                event_handler=EventHandler(),
            ) as stream:
                stream.until_done()
        finally:
            client.beta.assistants.delete(assistant.id)
        break
