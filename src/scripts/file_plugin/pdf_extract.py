import os
import logging
from PyPDF2 import PdfFileReader
from tools import calculate_token_size

PRIORITY = 1


class CreatePlugin(object):
    def __init__(self):
        self.target_ext = [".pdf"]
        self.description = "PDFファイルからテキストを抽出します"

    def run(self, message, input_file):
        response_files = []
        base = os.path.splitext(input_file)[0]
        # PDFファイルを開く
        with open(input_file, "rb") as file:
            pdf = PdfFileReader(file)
            text = ""
            # 各ページからテキストを抽出
            for page in range(pdf.getNumPages()):
                text += pdf.getPage(page).extractText()
            # 抽出したテキストをupload_filesとresponse_filesに追加
            txt_file = f"{base}.txt"
            response_files.append(txt_file)
            with open(txt_file, "w") as f:
                f.write(text)
            message = f"{message}\n{text}"

        return response_files, message
