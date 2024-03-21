import os
import json
import logging
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

SERVICE_ACCOUNT_FILE = "/function/data/service_account.json"


def run(keyword):
    results = ""

    # スコープの設定
    SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]

    try:
        # サービスアカウント認証情報の取得
        credentials = service_account.Credentials.from_service_account_file(
            SERVICE_ACCOUNT_FILE, scopes=SCOPES
        )

        # Google Drive API クライアントの構築
        service = build("drive", "v3", credentials=credentials)

        # キーワードが含まれるファイルを検索するためのクエリ
        query = f"name contains '{keyword}'"

        # ファイルリストの取得
        response = service.files().list(q=query).execute()

        # 結果の表示
        resp = response.get("files", [])
        if len(resp) > 0:
            results = f"## Google Driveで[{keyword}]に関連したファイル\n"
        for file in resp:
            if file.get("mimeType") == "application/vnd.google-apps.folder":
                url = f"https://drive.google.com/drive/folders/{file.get('id')}?usp=drive_link"
            else:
                url = f"https://drive.google.com/file/d/{file.get('id')}/view?usp=drive_link"
            results += f"* [{file.get('name')}]({url})\n"

    except HttpError as error:
        # Google Drive APIが無効の場合のエラー処理
        if error.resp.status in [403, 404]:
            logging.error(
                "Google Drive APIが無効またはアクセスできません。APIを有効にするか、プロジェクトの設定を確認してください。"
            )
            return "Google Drive APIが無効またはアクセスできません。\nAPIを有効にするか、プロジェクトの設定を確認してください。"
        else:
            logging.error(f"予期せぬエラーが発生しました: {error}")

    except Exception as e:
        # その他のエラー
        logging.error(f"エラーが発生しました: {e}")
    return results
