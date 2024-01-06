import os
import logging
import subprocess
from tempfile import mkdtemp
from openai import OpenAI

PRIORITY = 1


def audio_to_text(audio_file):
    client = OpenAI()
    text = ""
    with open(audio_file, "rb") as audio:
        transcript = client.audio.transcriptions.create(model="whisper-1", file=audio)
        text = transcript.text
    return text


class CreatePlugin(object):
    def __init__(self):
        self.target_ext = [".mp3", ".mp4", ".mpeg", ".mpga", ".m4a", ".wav", ".webm"]
        self.description = "音声ファイルをテキストファイルに変換します。"

    def run(self, message, input_file):
        output_files = []
        response_files = []
        if os.path.getsize(input_file) > 25000000:  # 25MB以上の場合
            try:
                base_name = os.path.splitext(os.path.basename(input_file))[0]
                output_format = f"{base_name}%03d.mp3"
                segment_time = 60 * 20  # 20分
                command = [
                    "ffmpeg",
                    "-i",
                    input_file,
                    "-vn",
                    "-f",
                    "segment",
                    "-segment_time",
                    str(segment_time),
                    "-b:a",
                    "128k",
                    output_format,
                ]
                subprocess.run(command, check=True)
                # 分割されたファイル名を取得
                for i in range(1000):  # 1000ファイルまで対応
                    output_file = output_format % i
                    if os.path.exists(output_file):
                        output_files.append(output_file)
                    else:
                        break
            except Exception as e:
                logging.error(e)
                return []

            logging.info(f"convert {', '.join(output_files)}")
        else:
            output_files.append(input_file)

        # 音声ファイルをテキストに変換
        transcript = ""
        for output_file in output_files:
            transcript += audio_to_text(output_file)

        # テキストファイルを出力
        base = os.path.splitext(input_file)[0]
        text_file = os.path.join(mkdtemp(), f"{base}.txt")
        with open(text_file, "w") as f:
            f.write(f"# {os.path.basename(input_file)}の文字起こし\n{transcript}")
        response_files.append(text_file)
        return response_files, message
