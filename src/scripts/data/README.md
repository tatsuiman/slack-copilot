以下はYaraルールでメッセージを検査し、マッチした場合は該当するファイルやURLを提供するチャットボットシステムの設定ファイルのサンプルです。

* message.yara
```
rule sample_guide
{
    strings:
        $keyword1 = "sample1"
        $keyword2 = "sample2"
        $keyword3 = "sample3"

    condition:
        ($keyword1 and $keyword2) or $keyword3
}
```

* assistant.yaml
  * model
    - gpt-4-turbo-preview
  * tools
    - 定義済みpython関数
      - google_search
      - slack_search
      - notion_search
      - github_search
      - google_drive_search

```yaml
sample_guide:
  name: サンプルガイド
  model: gpt-4-turbo-preview
  instructions: |
    あなたはサンプルの質問に回答するアシスタントです。
  urls:
    - url: https://example1.com
      file: index.html
    - url: https://example2.com
      file: index.html
  files:
    - sample1.pdf
    - sample2.pdf
  tools:
   - function:
       description: Search Google
       name: simple_search
       parameters:
         properties:
           keyword:
             description: Short single keyword without line breaks
             type: string
         required:
         - keyword
         type: object
     type: function
```

* simple_search.py
```python
def run(keyword: str) -> str:
    return "search result here"
```
