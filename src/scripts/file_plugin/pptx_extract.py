import os
import logging
import subprocess
from tempfile import mkdtemp

PRIORITY = 0


class CreatePlugin(object):
    def __init__(self):
        self.target_ext = [".pptx", ".ppt"]
        self.description = "PPTXファイルから画像を抽出します"

    def run(self, message, input_file):
        response_files = []
        temp_dir = mkdtemp()
        base = os.path.splitext(os.path.basename(input_file))[0]
        pdf_file = os.path.join(temp_dir, f"{base}.pdf")
        png_file_base = os.path.join(temp_dir, base)
        logging.info(f"convert {input_file} -> {pdf_file}")
        subprocess.run(
            [
                "libreoffice",
                "--headless",
                "--convert-to",
                "pdf",
                input_file,
                "--outdir",
                temp_dir,
            ],
            check=True,
        )

        logging.info(f"convert {pdf_file} -> {png_file_base}-*.png")
        # pdfを画像ファイルに変換
        subprocess.run(
            [
                "pdftoppm",
                "-png",
                pdf_file,
                png_file_base,
            ],
            check=True,
        )
        png_files = [
            os.path.join(temp_dir, f)
            for f in os.listdir(temp_dir)
            if f.endswith(".png")
        ]
        png_files.sort()
        logging.info(f"png files: {png_files}")
        # upload_filesにpng画像を追加
        for png_file in png_files:
            response_files.append(png_file)

        return response_files, message
