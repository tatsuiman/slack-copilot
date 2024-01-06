import os
import logging
import subprocess
from tempfile import mkdtemp

PRIORITY = 0


class CreatePlugin(object):
    def __init__(self):
        self.target_ext = [".zip"]
        self.description = "zipファイルを展開します"

    def run(self, message, input_file):
        response_files = []
        base = os.path.splitext(input_file)[0]
        # mkdtempで一時ディレクトリを作成
        temp_dir = mkdtemp()
        # zipファイルを展開
        # パスワードリストを3パターン用意
        password_list = ["infected", "password", "malware"]
        # パスワード付きzip とパスワード無しzip両方を試す
        for password in password_list:
            try:
                subprocess.run(
                    ["unzip", "-P", password, "-o", input_file, "-d", temp_dir],
                    check=True,
                )
                break
            except Exception as e:
                continue
        else:
            # パスワード無しで試す
            subprocess.run(["unzip", "-o", input_file, "-d", temp_dir], check=True)
        for root, dirs, files in os.walk(temp_dir):
            extract_files = []
            for file in files:
                # 表示用のファイル名
                extract_files.append(os.path.join(root.replace(temp_dir, ""), file))
            for file in files:
                extract_file = os.path.join(root, file)
                # 20ファイルだけを処理
                if len(response_files) < 20:
                    response_files.append(extract_file)
            logging.info(f"extract files: {extract_files}")
        message = f"{message}\n# {os.path.basename(input_file)}の展開結果\n`{','.join(extract_files)}`"
        return response_files, message
