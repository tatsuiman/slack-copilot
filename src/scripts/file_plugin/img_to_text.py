import os
import logging
import PIL.Image
import google.generativeai as genai

PRIORITY = 1
DEBUG = os.getenv("DEBUG", "false").lower() == "true"


class CreatePlugin(object):
    def __init__(self):
        self.target_ext = [".png", ".jpg", ".jpeg"]
        self.description = "画像ファイルをテキストに変換します"

    def run(self, message, input_file):
        response_files = []
        base = os.path.splitext(input_file)[0]
        # ファイルサイズが4MB以上の場合は処理を中断
        if os.path.getsize(input_file) > 4 * 1024 * 1024:
            logging.error("ファイルサイズが大きすぎます。4MB以下のファイルをアップロードしてください。")
            return response_files, message
        if DEBUG:
            md_file = f"{base}.md"
            with open(md_file, "w") as f:
                f.write("test")
            response_files.append(md_file)
            return response_files, message

        # モデルの準備
        model = genai.GenerativeModel("gemini-pro-vision")
        # 画像の読み込み
        img = PIL.Image.open(input_file)
        # 推論の実行
        response = model.generate_content(
            [
                "画像がスライドや文章の場合はMarkdownで構造化して説明してください。それ以外の場合は画像内のオブジェクトについてできるだけ詳細に説明してください。",
                img,
            ],
            stream=True,
        )
        response.resolve()
        text = f"## {os.path.basename(input_file)} についての説明\n {response.text}"
        md_file = f"{base}.md"
        with open(md_file, "w") as f:
            f.write(text)
        response_files.append(md_file)
        message = f"{message}\n{text}"
        return response_files, message
