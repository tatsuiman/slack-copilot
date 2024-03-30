import os
import sys
import time
import boto3
from openai import OpenAI
from pinecone import Pinecone
from pinecone import Pinecone, PodSpec

pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
client = OpenAI()

index_name = "semantic-search-openai"
MODEL = "text-embedding-3-small"

if index_name not in pc.list_indexes().names():
    # if does not exist, create index
    # ref: https://docs.pinecone.io/guides/indexes/create-an-index#create-a-pod-based-index
    pc.create_index(
        index_name,
        dimension=1536,  # dimensionality of text-embed-3-small
        metric="dotproduct",
        spec=PodSpec(environment="gcp-starter"),
    )
    # wait for index to be initialized
    while not pc.describe_index(index_name).status["ready"]:
        time.sleep(1)

# connect to index
index = pc.Index(index_name)
time.sleep(1)

# DynamoDB Client
dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table("open-slack-ai-dev-slack-message")
# すべてのデータをスキャン
for item in table.scan()["Items"]:
    thread_id = item["thread_id"]
    client = OpenAI(timeout=20.0, max_retries=3)
    messages = client.beta.threads.messages.list(
        thread_id=thread_id,
        order="asc",
    ).data
    # 最低でも4メッセージ含まれるスレッドを抽出
    if len(messages) < 4:
        continue
    data = ""
    print(f"{thread_id}")
    thread = client.beta.threads.retrieve(thread_id=thread_id)
    for message in messages:
        for content in message.content:
            if content.type == "text":
                data += f"{content.text.value}\n"

    # ベクトル化
    res = client.embeddings.create(
        input=[data],
        model=MODEL,
    )
    embed = client.embeddings.create(input=data, model=MODEL).data[0].embedding

    # 元データとベクトルデータが1:1の関係になる場合、idを使ってデータを更新することができます。
    res = index.upsert(
        vectors=[
            {
                "id": thread_id,
                "values": embed,
                "metadata": {"created_at": thread.created_at},
            }
        ],
    )
