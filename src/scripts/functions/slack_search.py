import os
import json
import logging
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from notion.util import get_page_markdown


def run(keyword: str) -> str:
    """Slackのメッセージと関連情報を検索できます。検索キーワードとなる日本語の文字列を入力してください。"""

    # Slackクライアントの初期化
    client = WebClient(token=os.getenv("SLACK_USER_TOKEN"))

    try:
        # メッセージを検索
        resp = client.search_messages(query=keyword)

        # 検索結果を返す
        if resp.status_code == 200:
            messages = ""
            md_content = ""
            if resp["ok"]:
                for message in resp["messages"]["matches"]:
                    if (
                        message["type"] != "message"
                        and message["channel"]["is_private"] == False
                        and message["channel"]["is_mpim"] == False
                        and message["channel"]["is_group"] == False
                        and message["channel"]["is_im"] == False
                    ):
                        continue
                    logging.debug(f'{message["permalink"]}\n')
                    messages += f"<@{message['user']}>: {message['text']}\n"
                    md_content += get_page_markdown(message["text"], recursive=False)

                # レスポンスの作成
                res = f"#チャット履歴\n{messages}\n---\n# 関連情報\n{md_content}"
                return res
            else:
                return resp["error"]

    except SlackApiError as e:
        # エラーが発生した場合
        return f"Error searching messages: {str(e)}"
    return "Slackの検索結果は何も見つかりませんでした。"
