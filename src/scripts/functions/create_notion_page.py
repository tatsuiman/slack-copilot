import os
from notion.util import (
    create_notion_page,
    markdown_to_notion_blocks,
    append_blocks_to_page,
)

# NotionデータベースID
DATABASE_ID = os.getenv("DATABASE_ID")


def run(title, content):
    # 新しいページを作成
    properties = {}
    resp = create_notion_page(DATABASE_ID, title, properties)
    try:
        # MarkdownをNotionブロックに変換
        blocks = markdown_to_notion_blocks(content)
        # Notionページにブロックを追加
        append_blocks_to_page(resp["id"], blocks)
        url = resp["url"]
        return f"\nNotionページを作成しました。\n\n間違いがあれば修正し、ページは適当な場所に移動してください。\n{title}\n{url}"
    except:
        return f"\nNotionページの追加に失敗しました。{resp}"
