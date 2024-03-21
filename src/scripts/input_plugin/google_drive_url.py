import os
import re
import csv
import logging
from tempfile import mkdtemp
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

DESCRIPTION = "Google DriveのURLからファイルをダウンロード"
SERVICE_ACCOUNT_FILE = "/function/data/service_account.json"


def get_sheets(spreadsheet_id):
    files = []
    # スコープの設定
    SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

    # 認証とサービスの構築
    credentials = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE, scopes=SCOPES
    )
    service = build("sheets", "v4", credentials=credentials)

    try:
        # スプレッドシートのメタデータを取得してシート名を取得
        sheet_metadata = (
            service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
        )
        sheets = sheet_metadata.get("sheets", "")

        # 一時ディレクトリの作成
        temp_dir = mkdtemp()

        for sheet in sheets:
            title = sheet.get("properties", {}).get("title")
            sheet_id = sheet.get("properties", {}).get("sheetId")
            # 空のセル以外の範囲を自動で取得
            result = (
                service.spreadsheets()
                .values()
                .get(spreadsheetId=spreadsheet_id, range=title)
                .execute()
            )
            values = result.get("values", [])

            if values:
                # 一時ディレクトリにシート名のcsvファイルを出力
                temp_file_path = os.path.join(temp_dir, f"{title}.csv")
                with open(temp_file_path, "w", newline="") as csvfile:
                    writer = csv.writer(csvfile)
                    for row in values:
                        writer.writerow(row)
                files.append(temp_file_path)
    except Exception as e:
        logging.error(f"エラーが発生しました: {e}")

    return files


def run(message):
    files = []
    prompt = ""
    try:
        # Regular expression pattern to extract file_id from the Google Drive URL
        pattern_drive = r"https://drive.google.com/file/d/([a-zA-Z0-9_-]+)/"
        pattern_sheets = r"https://docs.google.com/spreadsheets/d/([a-zA-Z0-9_-]+)/"
        # Extracting the file_id using regular expression
        matches_drive = re.findall(pattern_drive, message)
        matches_sheets = re.findall(pattern_sheets, message)
        matches = matches_drive + matches_sheets
        if matches:
            # スコープの設定
            SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]

            # サービスアカウント認証情報の取得
            credentials = service_account.Credentials.from_service_account_file(
                SERVICE_ACCOUNT_FILE, scopes=SCOPES
            )

            # Google Drive API クライアントの構築
            service = build("drive", "v3", credentials=credentials)

            # Checking if file_id is found and displaying it
            for file_id in matches:
                # Google Sheets
                sheet_files = get_sheets(spreadsheet_id=file_id)
                if sheet_files:
                    for sheet_file in sheet_files:
                        files.append(sheet_file)
                        prompt += f"Google Sheetsを{os.path.basename(sheet_file)}に変換しました。\n"
                    continue

                # ファイルのメタデータを取得
                file_metadata = service.files().get(fileId=file_id).execute()
                file_name = file_metadata.get("name")
                logging.info(f"Downloading file: {file_name}")

                # ファイルダウンロードのリクエスト
                request = service.files().get_media(fileId=file_id)

                # ファイルを直接ディスクに書き込む
                file_path = os.path.join(mkdtemp(), file_name)
                with open(file_path, "wb") as f:
                    downloader = MediaIoBaseDownload(f, request)
                    done = False
                    while not done:
                        status, done = downloader.next_chunk()
                        logging.info(f"Download {int(status.progress() * 100)}%.")

                # プロンプトとファイルを追加
                files.append(file_path)
                prompt += f"Google Driveから{os.path.basename(file_name)}をダウンロードしました。\n"
    except Exception as e:
        # エラーハンドリング
        logging.error(f"エラーが発生しました: {e}")
        prompt += f"Googleドライブのファイルを開く際にエラーが発生しました: {e}"

    return prompt, files
