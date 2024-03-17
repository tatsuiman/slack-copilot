from blockkit import (
    Divider,
    Input,
    Message,
    PlainTextInput,
    Button,
    Actions,
    Section,
)


def generate_faq_block():
    elements = [
        Button(
            action_id="notion_button",
            text=":memo: Notionページ作成",
            value="notion",
            style="primary",
        ),
        Button(
            action_id="unresolve_button",
            text=":face_with_monocle: 問題が未解決です",
            value="unresolve",
        ),
        Button(
            action_id="contradiction_button",
            text=":face_with_one_eyebrow_raised: 潜在的な問題や矛盾点を探す",
            value="contradiction",
        ),
        Button(
            action_id="search_button",
            text=":slack: 関連する内容を探す",
            value="search",
        ),
        Button(
            action_id="google_search_button",
            text=":mag: googleで検索",
            value="google_search",
        ),
    ]
    payload = Message(
        blocks=[
            Actions(elements=elements),
        ]
    ).build()
    blocks = payload["blocks"]
    return blocks


def generate_completion_block(completion: str):
    elements = [
        Button(
            action_id="stop_button",
            text=":black_square_for_stop: 停止",
            value="stop",
        )
    ]
    payload = Message(
        blocks=[
            Section(text=completion),
            Divider(),
            Actions(elements=elements),
        ]
    ).build()
    blocks = payload["blocks"]
    return blocks


def generate_step_block(completion: str):
    payload = Message(
        blocks=[
            Section(text=completion),
        ]
    ).build()
    blocks = payload["blocks"]
    return blocks


def generate_unfurl_message():
    elements = [
        Button(
            action_id="ask_button",
            text="送信",
            value="ask",
            style="primary",
        )
    ]
    return Message(
        blocks=[
            Input(
                element=PlainTextInput(
                    action_id="ask-action",
                    placeholder="質問や回答内容が他の人に見られる心配はありません",
                ),
                label="リンクの内容についてAIに質問してみましょう",
            ),
            Actions(elements=elements),
        ],
    ).build()


def generate_api_key_input_message():
    elements = [
        Button(
            action_id="send_api_key",
            text="送信",
            value="api-key",
            style="primary",
        )
    ]
    payload = Message(
        blocks=[
            Input(
                element=PlainTextInput(
                    action_id="input-api-key",
                    placeholder="入力されたAPIキーは他の人からは見えません",
                ),
                label="APIキーを入力してください",
            ),
            Actions(elements=elements),
        ],
    ).build()
    blocks = payload["blocks"]
    return blocks
