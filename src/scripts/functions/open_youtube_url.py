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


if __name__ == "__main__":
    r = run(sys.argv[1])
    print(r)
