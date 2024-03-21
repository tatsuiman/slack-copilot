# 関数

Function Calling から呼び出される関数です。
`/`コマンドで指定したアシスタントが実行可能な関数を定義できます

## サンプル
`function/`に以下のようなpythonファイル`my_youtube_transcript.py`を作成してください
```python
import os
import sys
import logging
from youtube_transcript_api import YouTubeTranscriptApi

def run(url, language=["ja"]):
    video_id = url.split("=")[-1] if "=" in url else url.split("/")[-1]
    # 字幕リストを取得
    transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
    # 英語字幕は"en"に変更
    transcript = transcript_list.find_generated_transcript(language)
    text = ""
    transcript_text = ""
    for d in transcript.fetch():
        text = d["text"]
        transcript_text += f"{text}\n"
    return transcript_text
```

次に`data/assistant.yml`に以下のように追記します。
```yaml
youtube_transcript:
  name: 
  instructions: |
    Youtube URLから字幕を生成し質問に回答するアシスタントです
  tools:
    - function:
        description: Open Youtube URL
        name: my_youtube_transcript
        parameters:
          properties:
            url:
              description: youtube url string
              type: string
          required:
            - url
          type: object
      type: function
```

再度デプロイを行うとアシスタントと関数が追加されます
```bash
sls deploy
```