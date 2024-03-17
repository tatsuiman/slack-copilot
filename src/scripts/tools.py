import os
import tiktoken
import logging
import time
import re
from bs4 import BeautifulSoup
from selenium import webdriver


def truncate_strings(text, max_tokens):
    enc = tiktoken.encoding_for_model("gpt-4")
    encode_strings = enc.encode(text, allowed_special="all")
    encode_strings = encode_strings[:max_tokens]
    return enc.decode(encode_strings)


def calculate_token_size(text):
    # TikTokのAPIやライブラリを使用して実際のトークンサイズを計算
    encoding = tiktoken.encoding_for_model("gpt-4")
    return len(encoding.encode(text, allowed_special="all"))


def truncate_token_size(text, max_tokens):
    origin_token_size = calculate_token_size(text)
    truncated_text = truncate_strings(text, max_tokens)
    token_size = calculate_token_size(truncated_text)
    truncated_token_size = origin_token_size - token_size
    return truncated_text, token_size, truncated_token_size


def browser_open(url, screenshot_png=None):
    content = ""
    page_source = ""
    title = ""
    WEBDRIVER_TIMEOUT = 10
    WEBDRIVER_ARGUMENTS = (
        "--headless",
        "--no-sandbox",
        "--single-process",
        "--disable-dev-shm-usage",
        "--disable-gpu",
        "--disable-extensions",
        "--disk-cache-size=0",
        "--aggressive-cache-discard",
        "--disable-notifications",
        "--disable-remote-fonts",
        "--window-size=1366,768",
        "--hide-scrollbars",
        "--disable-audio-output",
    )
    try:
        # Selenium WebDriverの設定
        options = webdriver.ChromeOptions()
        service = webdriver.ChromeService("/opt/chromedriver-linux64/chromedriver")
        options.binary_location = "/opt/chrome-linux64/chrome"

        for opt in WEBDRIVER_ARGUMENTS:
            options.add_argument(opt)

        driver = webdriver.Chrome(options=options, service=service)
        driver.set_page_load_timeout(WEBDRIVER_TIMEOUT)

        # HTMLファイルを開く
        driver.get(url)
        time.sleep(10)  # レンダリングに時間を与える

        # ページのコンテンツを取得
        page_source = driver.page_source
        soup = BeautifulSoup(page_source, "html.parser")
        # scriptやstyle及びその他タグの除去
        for s in soup(["script", "style"]):
            s.decompose()
        title = soup.title.string if soup.title else "タイトルなし"
        content = soup.get_text()
        content = re.sub(r"\n+", "\n", content)

        # スクリーンショットを保存
        if screenshot_png is not None:
            driver.save_screenshot(screenshot_png)

        # ブラウザを閉じる
        driver.quit()
    except Exception as e:
        logging.error(e)

    return title, content
