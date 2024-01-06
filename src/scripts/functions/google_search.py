import os
import logging
from googleapiclient.discovery import build

# https://note.com/npaka/n/nd9a4a26a8932
GOOGLE_CSE_ID = os.getenv("GOOGLE_CSE_ID")
GOOGLE_API_KEY = os.getenv("GOOGLE_SEARCH_API_KEY")


def run(keyword):
    # Google Search APIを使って各キーワードを検索
    service = build("customsearch", "v1", developerKey=GOOGLE_API_KEY)
    results = ""
    res = service.cse().list(q=keyword, cx=GOOGLE_CSE_ID).execute()
    items = list(res.get("items", []))
    logging.info(f"hit {len(items)} urls")
    for item in items:
        # print(item)
        results += f'* title: "{item["title"]}"\n'
        results += f'  - snippet: `{item["snippet"]}`\n'
        results += f'  - url: "{item["formattedUrl"]}"\n\n'
    return results
