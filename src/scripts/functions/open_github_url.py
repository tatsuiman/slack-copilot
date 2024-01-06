import os
import requests


def run(url):
    GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
    if not GITHUB_TOKEN:
        return "GITHUB_TOKENが設定されていません。"

    headers = {"Authorization": f"token {GITHUB_TOKEN}"}
    # GitHubのURLをrawのURLに変換
    if "/pull/" in url or "/issues/" in url or "/commit/" in url:
        # PRまたはIssueまたはcommitのURLの場合、APIを使用して内容を取得
        api_url = url.replace("https://github.com", "https://api.github.com/repos")
        if "/pull/" in url:
            api_url = api_url.replace("/pull/", "/pulls/")
            response = requests.get(api_url, headers=headers)
            if response.status_code == 200:
                data = response.json()
                return data["body"]
        elif "/commit/" in url:
            api_url = api_url.replace("/commit/", "/commits/")
            response = requests.get(api_url, headers=headers)
            if response.status_code == 200:
                data = response.json()
                commiter = data["commit"]["committer"]
                files = [file["filename"] for file in data["files"]]
                files = "\n".join(files)
                commit_message = data["commit"]["message"]
                return f"## commiter\n{commiter}\n## commit message\n{commit_message}\n## files\n{files}"
        else:
            return "内容を取得できませんでした。"
    else:
        raw_url = url.replace("github.com", "raw.githubusercontent.com").replace(
            "/blob", ""
        )
        response = requests.get(raw_url, headers=headers)
        github_content = response.text
        return github_content
