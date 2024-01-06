import os
import re
import graphviz
import logging
from tools import browser_open
from tempfile import mkdtemp


def run(text):
    """
    テキストからmermaidまたはdotスクリプトを抽出し、そのタイプを返す関数
    """
    files = []
    pattern = re.compile(r"```(mermaid|dot|graphviz)\n(.*?)```", re.DOTALL)
    scripts = pattern.findall(text)
    for script_type, script in scripts:
        if script_type == "mermaid":
            mermaid_png_file = mermaid_to_image(script)
            if mermaid_png_file:
                files.append(mermaid_png_file)
        if script_type in ["dot", "graphviz"]:
            dot_png_file = dot_to_image(script)
            if dot_png_file:
                files.append(dot_png_file)
    return files


def dot_to_image(dot_code):
    png_file = os.path.join(mkdtemp(), "dot")
    try:
        # DOT言語でグラフを作成し、PNGとしてエクスポートする
        graph = graphviz.Source(dot_code)
        graph.render(png_file, format="png")
    except Exception as e:
        logging.error(e)
        return
    return f"{png_file}.png"


def mermaid_to_image(mermaid_script):
    png_file = os.path.join(mkdtemp(), "mermaid.png")
    # HTMLテンプレートを生成
    html_template = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Mermaid</title>
    <script src="https://cdn.jsdelivr.net/npm/mermaid@10.6.1/dist/mermaid.min.js"></script>
    <script>mermaid.initialize({{startOnLoad:true}});</script>
</head>
<body>
    <div class="mermaid">
    {mermaid_script}
    </div>
</body>
</html>
"""
    # HTMLファイルを保存
    html_file = f"{mkdtemp()}_mermaid_chart.html"
    with open(html_file, "w") as file:
        file.write(html_template)

    url = "file://" + os.path.abspath(html_file)
    content = browser_open(url, png_file)
    return png_file


if __name__ == "__main__":
    message = """
    ```graphviz
    digraph INC_Ransomware {
        rankdir=LR
        node [shape=box]
        start [shape=oval, label="攻撃開始"]
        credentials [label="認証情報の漏洩利用"]
        access [label="被害者の環境へのアクセス"]
        rdp [label="RDPを使ったラテラルムーブメント"]
        hacking [label="新しい端末をハッキング"]
        credential_stealing [label="追加の認証情報窃取コマンド実行"]
        ransomware_deployment [label="WMICとPSEXECを使用したランサムウェア導入"]
        data_exfiltration [label="データ流出(MegaSyncツール利用)"]
        leak_blog [label="リークブログでの情報公開"]
        negotiation_site [label="被害者向け交渉サイト提供"]
        ransom_note [label="身代金要求書の生成と表示"]
        data_encryption [label="ファイル暗号化"]
        end [shape=oval, label="攻撃完了"]

        start -> credentials
        credentials -> access -> rdp -> hacking -> credential_stealing -> ransomware_deployment -> data_encryption
        ransomware_deployment -> data_exfiltration
        data_exfiltration -> leak_blog
        data_encryption -> ransom_note
        ransom_note -> negotiation_site
        negotiation_site -> end
    }
    ```
    """
    # メソッドをテスト
    r = run(message)
    print(r)
