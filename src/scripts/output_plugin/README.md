# 出力プラグイン

出力された回答からファイルを抽出するプラグインです。
例えば以下のようなプラグインを作成するとhtmlのコードブロックが回答された場合に、
チャットボットは`.html`ファイルにコードブロックの中身を書き込んでアタッチメントファイル付きのメッセージを返信します。

## サンプル
```python
def run(text):
    files = []
    pattern = re.compile(r"```(html)\n(.*?)```", re.DOTALL)
    scripts = pattern.findall(text)
    for script_type, script in scripts:
        if script_type == "html":
            file = os.path.join(mkdtemp(), "sample.html")
            with open(file, "w") as f:
                f.write(script)
            files.append(file)
    return files
```

