import os
import json
import logging
from github import Github

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
ORGANIZATION_NAME = os.getenv("GITHUB_ORG")  # 組織アカウント名を設定


def run(keyword: str) -> str:
    g = Github(GITHUB_TOKEN)
    # IssueやPRとソースコードを検索
    issue_query = f"org:{ORGANIZATION_NAME} {keyword} in:title,body"
    pr_query = f"org:{ORGANIZATION_NAME} {keyword} in:title,body,type:pr"
    code_query = f"org:{ORGANIZATION_NAME} {keyword} in:file"
    issue_results = list(g.search_issues(issue_query, state="all"))
    pr_results = list(g.search_issues(pr_query, state="all"))
    code_results = list(g.search_code(code_query))

    results = "# Githubの検索結果\n"
    # Issueの結果を追加
    for issue in issue_results:
        results += f"* [{issue.title}]({issue.html_url})\n"
    # PRの結果を追加
    for pr in pr_results:
        results += f"* [{pr.title}, URL: {pr.html_url}\n"
    # コードの結果を追加
    for code in code_results:
        results += f"* {code.html_url}\n"

    if len(issue_results) == 0 and len(pr_results) == 0 and len(code_results) == 0:
        return "Githubの検索結果は何も見つかりませんでした。"
    else:
        return results


if __name__ == "__main__":
    keyword = "python"
    print(run(keyword))
