import os
import re
import logging
from tempfile import mkdtemp
from google.oauth2 import service_account
from google.auth import default as app_default_credentials
from google.auth import impersonated_credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

PRIORITY = 2
DESCRIPTION = "Google DriveのURLからファイルをダウンロード"


def run(event):
    message = event["text"]
    files = []
    processed = False
    try:
        # Regular expression pattern to extract file_id from the Google Drive URL
        pattern = r"https://drive.google.com/file/d/([a-zA-Z0-9_-]+)/"
        # Extracting the file_id using regular expression
        matches = re.findall(pattern, message)
        if not matches:
            return event, files, processed

        # スコープの設定
        SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]

        credentials, default_project_id = app_default_credentials(scopes=SCOPES)

        # Google Drive API クライアントの構築
        service = build("drive", "v3", credentials=credentials)

        # Checking if file_id is found and displaying it
        for file_id in matches:
            processed = True
            # ファイルのメタデータを取得
            file_metadata = service.files().get(fileId=file_id).execute()
            file_name = file_metadata.get("name")
            logging.info(f"Downloading file: {file_name}")

            # ファイルダウンロードのリクエスト
            request = service.files().get_media(fileId=file_id)

            file_path = os.path.join(mkdtemp(), file_name)
            # ファイルを直接ディスクに書き込む
            with open(file_path, "wb") as f:
                downloader = MediaIoBaseDownload(f, request)
                done = False
                while not done:
                    status, done = downloader.next_chunk()
                    logging.info(f"Download {int(status.progress() * 100)}%.")

            files.append(file_path)
    except Exception as e:
        # エラーハンドリング
        logging.error(f"エラーが発生しました: {e}")

    event["text"] = message
    return event, files, processed
