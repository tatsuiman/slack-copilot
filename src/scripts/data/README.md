## 自動応答ルール

以下はYaraルールでメッセージを検査し、マッチした場合は自動応答する設定です。

* message.yara
```
rule sample_guide
{
    meta:
        message = "hello world."
        description = "自動応答ルールのサンプル"
    strings:
        $keyword1 = "sample1"
        $keyword2 = "sample2"
        $keyword3 = "sample3"

    condition:
        ($keyword1 and $keyword2) or $keyword3
}
```


## アシスタントの設定

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
