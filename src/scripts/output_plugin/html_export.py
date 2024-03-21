import re
import os
from tempfile import mkdtemp
from tools import browser_open


# テキストからHTMLスクリプトを抽出し、PNGファイルとして保存する関数
def run(text):
    files = []
    # HTMLブロックを抽出する正規表現パターン
    pattern = re.compile(r"```(html)\n(.*?)```", re.DOTALL)
    # テキストからHTMLスクリプトを抽出
    scripts = pattern.findall(text)
    # 抽出したスクリプトごとに処理
    for script_type, script in scripts:
        # スクリプトタイプがHTMLの場合
        if script_type == "html":
            # 一時HTMLファイルのパスを生成
            html_file = os.path.join(mkdtemp(), "output.html")
            with open(html_file, "w") as f:
                f.write(script)
            # ファイルのURLを生成
            url = "file://" + os.path.abspath(html_file)
            # 出力PNGファイルのパスを生成
            png_file = os.path.join(mkdtemp(), "html.png")
            # ブラウザを開いてPNGファイルを生成
            content = browser_open(url, png_file)
            files.append(png_file)
    return files  # 出力ファイルリストを返す
