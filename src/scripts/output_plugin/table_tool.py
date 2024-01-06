import os
from tempfile import mkdtemp


def run(markdown_text):
    csv_files = []
    # テーブル部分を抽出
    lines = markdown_text.strip().split("\n")
    table_lines = []
    table_started = False

    for line in lines:
        # テーブルの開始を検出
        if "|" in line and not table_started:
            table_started = True
        # テーブルの終了を検出
        if table_started and not "|" in line:
            break
        # テーブル行を追加
        if table_started:
            table_lines.append(line)

    # CSVデータを格納するリストを作成
    csv_data = []

    if table_lines:
        # ヘッダー行を処理
        headers = table_lines[0].split("|")[1:-1]
        csv_data.append(",".join(header.strip() for header in headers))
        # データ行を処理
        for line in table_lines[2:]:
            columns = line.split("|")[1:-1]
            csv_data.append(",".join(column.strip() for column in columns))

    if len(csv_data) > 1:
        csv_file_path = os.path.join(mkdtemp(), "table.csv")
        with open(csv_file_path, "w", encoding="utf-8") as file:
            file.write("\n".join(csv_data))
        csv_files.append(csv_file_path)

    return csv_files
