import os
import json
import logging
import boto3
from pluginbase import PluginBase
from slacklib import get_user_id
from ai import create_assistant

# PluginBase インスタンスを作成
plugin_base = PluginBase(package="plugins")
# 入力されたpromptに対する処理のプラグイン
input_plugin_source = plugin_base.make_plugin_source(searchpath=["./input_plugin"])
# 出力された応答に対する処理のプラグイン
output_plugin_source = plugin_base.make_plugin_source(searchpath=["./output_plugin"])
# ファイルに関するプラグイン
file_plugin_source = plugin_base.make_plugin_source(searchpath=["./file_plugin"])

logging.info(f"file plugins: {file_plugin_source.list_plugins()}")
logging.info(f"input plugins: {input_plugin_source.list_plugins()}")
logging.info(f"output plugins: {output_plugin_source.list_plugins()}")

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
        self._get_or_create_assistant()

    def _get_or_create_assistant(self):
        # DynamoDBからAssistant IDを取得
        table = dynamodb.Table(DB_USERS_TABLE)
        response = table.get_item(Key={"user_id": self.user_id})
        if "Item" in response:
            # ドキュメントIDが存在する場合はAssistant IDを取得する
            self.assistant_id = response["Item"].get("assistant_id")
            self.level = int(response["Item"].get("level", 0))
            logging.info(f"exists assistant: {self.assistant_id}")
        else:
            # 新しいアシスタントを作成する
            user_info = get_user_id(self.user_id)
            username = user_info["user"]["real_name"]
            self.assistant_id = create_assistant(f"{username}'s Assistant")
            logging.info(f"new assistant: {self.assistant_id}")
            table.put_item(
                Item={
                    "user_id": self.user_id,
                    "assistant_id": self.assistant_id,
                    "level": self.level,
                }
            )

    def get_assistant_id(self):
        return self.assistant_id

    def get_level(self):
        return self.level

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


def get_thread_info(doc_id):
    table = dynamodb.Table(DB_MESSAGE_TABLE)
    doc = table.get_item(Key={"doc_id": doc_id})
    if "Item" in doc:
        return doc["Item"]
    return None


def update_thread_info(doc_id, item):
    item["doc_id"] = doc_id
    table = dynamodb.Table(DB_MESSAGE_TABLE)
    table.put_item(Item=item)


def publish_event(event):
    # イベントをSNSトピックに送信
    event_data = json.dumps({"default": json.dumps(event)})
    response = sns_client.publish(
        TopicArn=TOPIC_ARN, Message=event_data, MessageStructure="json"
    )
    # メッセージが正常に送信されたことを確認
    print(f"publish: {response['MessageId']}")
