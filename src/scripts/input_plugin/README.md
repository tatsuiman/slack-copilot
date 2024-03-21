# 入力プラグイン

入力されたメッセージからファイルを抽出するプラグインです。
例えば以下のようなプラグインを書いた場合、`prompt`の指示に基づいて`file1.csv`と`file2.csv`がCode Interpreterで読み込まれます。

## プラグインサンプル

```python
def run(message):
    prompt = "テキストファイルを抽出しました。"
    files = ["file1.csv", "file2.csv"]
    return prompt, files
```