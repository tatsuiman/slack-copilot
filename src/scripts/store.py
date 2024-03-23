import os
import yaml
import json
import logging
import boto3
from tempfile import mkdtemp
from slacklib import get_user_id
from ai import AssistantAPIClient
from tools import browser_open

# DynamoDB Client
dynamodb = boto3.resource("dynamodb")
# SNS Client
sns_client = boto3.client("sns")

# プライベートモードが無効の場合のアシスタントID
ASSISTANT_ID = os.getenv("ASSISTANT_ID", "none")

TOPIC_ARN = os.getenv("AWS_SNS_TOPIC_ARN")
DB_USERS_TABLE = os.getenv("DB_USERS_TABLE")
DB_MESSAGE_TABLE = os.getenv("DB_MESSAGE_TABLE")


class Assistant:
    def __init__(self, user_id):
        self.user_id = user_id
        self.assistant_id = None
        self.level = 0
        self.client = None
        self.assistant_name = "internal_search"
        self.api_key = os.getenv("OPENAI_API_KEY", "")
        self.table = dynamodb.Table(DB_USERS_TABLE)
        self._get_assistant()

    def _get_assistant(self):
        # DynamoDBからAssistant IDを取得
        response = self.table.get_item(Key={"user_id": self.user_id})
        if "Item" in response:
            # ドキュメントIDが存在する場合はAssistant IDを取得する
            self.assistant_id = response["Item"].get("assistant_id")
            self.level = int(response["Item"].get("level", 0))
            self.api_key = response["Item"].get("api_key", self.api_key)
            self.assistant_name = response["Item"].get(
                "assistant_name", self.assistant_name
            )
            if len(self.api_key) > 5:
                self.client = AssistantAPIClient(api_key=self.api_key)
            logging.info(f"exists assistant: {self.assistant_id}")

    def create_assistant(self, api_key):
        user_info = get_user_id(self.user_id)
        username = user_info["user"]["real_name"]
        self.api_key = api_key
        self.client = AssistantAPIClient(api_key=api_key)
        # 新しいアシスタントを作成する
        self.assistant_id = self.client.create_assistant(f"{username}'s Assistant")
        logging.info(f"new assistant: {self.assistant_id}")
        self.table.put_item(
            Item={
                "user_id": self.user_id,
                "assistant_id": self.assistant_id,
                "level": self.level,
                "api_key": self.api_key,
            }
        )

    def get_client(self):
        return self.client

    def get_assistant_id(self):
        return self.assistant_id

    def get_api_key(self):
        return self.api_key

    def get_level(self):
        return self.level

    def get_assistant_name(self):
        return self.assistant_name

    def update_level(self, level):
        # if self.level == level:
        #    return
        self.level = level
        table = dynamodb.Table(DB_USERS_TABLE)
        table.update_item(
            Key={"user_id": self.user_id},
            UpdateExpression="set #lvl = :l",
            ExpressionAttributeNames={"#lvl": "level"},
            ExpressionAttributeValues={":l": level},
        )

    def update_assistant_name(self, assistant_name):
        table = dynamodb.Table(DB_USERS_TABLE)
        table.update_item(
            Key={"user_id": self.user_id},
            UpdateExpression="set assistant_name = :n",
            ExpressionAttributeValues={":n": assistant_name},
        )

    def load_assistant_config(self):
        assistant_file = "/function/data/assistant.yml"
        # モデルを初期化
        assistant_config = {
            "model": "",
            "faq": [],
            "tools": [],
            "files": [],
            "instructions": "あなたはユーザに質問に回答するアシスタントです",
            "additional_instructions": "",
        }
        # アシスタントファイルを開き、データを読み込む
        with open(assistant_file, "r") as f:
            assistant_data = yaml.safe_load(f)
            assistant = assistant_data[self.assistant_name]
            instructions = assistant.get("instructions")
            assistant_config["model"] = assistant.get("model", "")
            assistant_config["faq"] = assistant.get("faq", [])
            assistant_config["tools"].extend(assistant.get("tools", []))
            assistant_config["instructions"] = assistant_config.get(
                "instructions", instructions
            )
            # ファイルを処理
            for file in assistant.get("files", []):
                filename = f"/function/data/{file}"
                if os.path.exists(filename):
                    assistant_config["files"].append(filename)
            # URLを処理
            for u in assistant.get("urls", []):
                url = u["url"]
                file = u["file"]
                title, content = browser_open(url)
                filename = os.path.join(mkdtemp(), file)
                with open(filename, "w") as f:
                    f.write(content)
                assistant_config["files"].append(filename)
        # モデルを返す
        return assistant_config


class ThreadStore:
    def __init__(self, doc_id):
        self.doc_id = doc_id

    def get_thread_info(self):
        table = dynamodb.Table(DB_MESSAGE_TABLE)
        doc = table.get_item(Key={"doc_id": self.doc_id})
        if "Item" in doc:
            return doc["Item"]
        return None

    def update_thread_info(self, item):
        item["doc_id"] = self.doc_id
        table = dynamodb.Table(DB_MESSAGE_TABLE)
        table.put_item(Item=item)

    def update_run_id(self, run_id):
        table = dynamodb.Table(DB_MESSAGE_TABLE)
        table.update_item(
            Key={"doc_id": self.doc_id},
            UpdateExpression="set run_id = :r",
            ExpressionAttributeValues={":r": run_id},
        )


def publish_event(event):
    # イベントをSNSトピックに送信
    event_data = json.dumps({"default": json.dumps(event)})
    response = sns_client.publish(
        TopicArn=TOPIC_ARN, Message=event_data, MessageStructure="json"
    )
    # メッセージが正常に送信されたことを確認
    print(f"publish: {response['MessageId']}")
