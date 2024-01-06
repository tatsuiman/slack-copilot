import logging
from notion.util import get_page_markdown


def run(url):
    page_content = get_page_markdown(url, recursive=True)
    return page_content
