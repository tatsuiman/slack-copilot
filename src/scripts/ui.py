import yaml
from blockkit import (
    Divider,
    Input,
    Message,
    PlainTextInput,
    Button,
    Actions,
    Section,
    Home,
    Header,
    PlainOption,
    StaticSelect,
)
from ai import CODE_INTERPRETER_EXTS


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


def generate_home():
    blocks = []
    blocks.append(Header(text="自動で入力される文脈"))
    for context in [
        "スレッドのメッセージ",
        "チャンネル内のcanvas",
        "アップロードされたファイル",
        "アクションの実行結果",
    ]:
        blocks.append(Section(text=f"• {context}\n"))
    blocks.append(Divider())
    blocks.append(Header(text="アップロード可能なファイル"))
    exts = [f"`{ext}`" for ext in CODE_INTERPRETER_EXTS]
    blocks.append(Section(text=f'• {", ".join(exts)}'))
    blocks.append(Section(text=f"• 任意のチャンネルのcanvas"))
    blocks.append(Section(text=f"• テキストのスニペット"))
    blocks.append(Divider())
    blocks.append(Header(text="アシスタントの一覧"))
    blocks.append(
        Section(text="`/` ショートカットからアシスタントを変更することが可能です。\n")
    )
    with open("/function/data/assistant.yml") as f:
        config = yaml.safe_load(f)
    for assistant_name, assistant in config.items():
        blocks.append(Header(text=assistant["name"]))
        blocks.append(Section(text=f'```指示:\n{assistant.get("instructions", "")}```'))
        for tool in assistant.get("tools", []):
            if tool["type"] == "function":
                function_name = tool["function"]["name"]
                function_description = tool["function"].get("description", "")
                blocks.append(
                    Section(text=(f"・ `{function_name}` ({function_description})\n"))
                )
        blocks.append(Divider())
    payload = Home(blocks=blocks).build()
    return payload


def generate_select_assistant_block():
    with open("/function/data/assistant.yml") as f:
        config = yaml.safe_load(f)
    options = []
    for assistant_name, assistant in config.items():
        options.append(PlainOption(text=assistant["name"], value=assistant_name))
    payload = Message(
        blocks=[
            Section(
                text="アシスタントを選択してください",
                accessory=StaticSelect(
                    action_id="assistant-select",
                    placeholder="未選択",
                    options=options,
                ),
            ),
        ]
    ).build()
    blocks = payload["blocks"]
    return blocks
