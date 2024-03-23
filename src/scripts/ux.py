from slacklib import (
    post_ephemeral,
    get_im_channel_id,
)
from blockkit import Message, Section

MAX_LEVEL = 6


def assistant_instructor(channel_id, process_ts, user_id, assistant_config, th, level):
    next_level = level
    thread_len = th.thread_len
    token_size = th.token_size
    files = th.files

    functions = [
        tool["function"]["name"]
        for tool in assistant_config["tools"]
        if tool["type"] == "function"
    ]
    demo_reaction = [
        {
            "message": (
                "次はGoogle検索を活用してみましょう。\n"
                "以下のように `slack` と `検索` というキーワードを含めて質問してみてください。\n"
                "例\n```関連する内容をslackで検索してください```"
            ),
            "ok": "google_search" in functions,
        },
        {
            "message": (
                "次はSlackのURLについて質問してみましょう。質問したいslackのURLをコピーして以下のように質問してみてください。\n"
                "例\n```次の会話内容を要約してください。\n"
                "https://xxxxxxx.slack.com/archives/D0XXXXXXXXX/p1706971999999999```"
            ),
            "ok": "open_slack_url" in functions,
        },
        {
            "message": (
                "次はGoogleの検索結果を活用してみましょう。\n"
                " `/` と入力して「アシスタントを変更」を選択し、「インターネット検索アシスタント」に変更した後、以下のように `google` と `検索` というキーワードを含めて質問してみてください。\n"
                "例\n```関連する内容をgoogleで検索してください```"
            ),
            "ok": "slack_search" in functions,
        },
        {
            "message": (
                "次は新しいスレッドで質問してみましょう。\n"
                "AIは会話をスレッド単位で記憶します。\n"
                "話題が変わる場合はバイアスを避けるために新しいスレッドを立てて質問してみてください。"
            ),
            "ok": thread_len <= 1,
        },
        {
            "message": (
                "次は500トークン以上の質問をしてみましょう。\n"
                "トークン数は質問の文字数が増えるほど増加し、トークン数が多いほど解答の精度が高くなる傾向があります。"
            ),
            "ok": token_size >= 500,
        },
        {
            "message": (
                "次はファイルの内容について質問してみましょう。\n"
                "ファイルのアップロードボタンから任意のファイルを共有して、その内容について質問してみてください。"
            ),
            "ok": len(files) > 0,
        },
        {
            "message": (
                "お疲れ様でした。最後に10メッセージ以上のスレッドで質問してみましょう。\n"
                "例\n```メッセージの内容を要約してください。```"
            ),
            "ok": thread_len >= 10,
        },
    ]
    if next_level >= len(demo_reaction):
        return next_level
    # レベルアップ
    if demo_reaction[level]["ok"]:
        next_level += 1
    # 進捗を計算
    progress = int(next_level / len(demo_reaction) * 100)
    emoji = ":beginner:" if progress < 50 else ":star:"
    # メッセージを作成
    if progress < 50:
        pre_message = f"{emoji} あなたは {progress}% しかAIを使いこなせていません。\n"
    else:
        pre_message = f"{emoji} あなたはすでに {progress}% AIを使いこなしています。\n"
    im_channel_id = get_im_channel_id(user_id)
    if next_level < len(demo_reaction):
        message = demo_reaction[next_level]["message"]
        text = (
            f"<@{user_id}>\n{pre_message}\n\n{message}\n話題を変える場合はスレッドを変えて質問してみてください。\n\n"
            f"詳しい使い方は<#{im_channel_id}|Slackアプリ>のホームから確認できます。"
        )
        payload = Message(blocks=[Section(text=text)]).build()
        post_ephemeral(
            channel_id,
            process_ts,
            user_id,
            blocks=payload["blocks"],
        )
    return next_level
