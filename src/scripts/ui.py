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


def generate_faq_block(questions=[]):
    elements = []
    for index, question in enumerate(questions[:5]):
        question["action_id"] = f"faq_button_{index}"
        elements.append(Button(**question))

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


def generate_home(assistant_name: str):
    blocks = []
    with open("/function/data/assistant.yml") as f:
        config = yaml.safe_load(f)
    current_assistant_name = config[assistant_name]["name"]
    blocks.append(Header(text="自動で入力される文脈"))
    for context in [
        "スレッドのメッセージ",
        "チャンネル内のcanvas",
        "アップロードされたファイル",
        "関数の実行結果",
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
    blocks.append(Section(text=f"現在のアシスタント: `{current_assistant_name}`\n"))

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
