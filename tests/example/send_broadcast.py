import os
import sys

sys.path.append("../../src/scripts")
from slack_sdk import WebClient
from slacklib import get_im_channel_id, BOT_USER_ID

slack_token = os.getenv("SLACK_BOT_TOKEN")
# Slackクライアントの初期化
client = WebClient(token=slack_token)

for user in client.users_list()["members"]:
    # botと削除されたユーザはスキップ
    if user["deleted"] or user["is_bot"] or user["id"] == "USLACKBOT":
        continue
    user_id = user["id"]
    real_name = user["real_name"]
    im_channel_id = get_im_channel_id(user_id)
    print(im_channel_id, user_id, real_name)
    message = (
        f"こんにちは、{real_name}さん。\n"
        f"SlackでChatGPTが利用できるようになりました。\n"
        f"なんでも自由に話しかけてください。\n"
        f"このチャンネル以外で話しかける時は<@{BOT_USER_ID}>をメンションしてください。"
    )
    res = client.chat_postMessage(
        channel=im_channel_id,
        text=message,
    )
