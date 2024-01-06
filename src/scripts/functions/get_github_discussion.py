import os
import requests


def run(github_url: str) -> str:
    owner, repo_name = github_url.split("/")[-2:]
    github_token = os.getenv("GITHUB_TOKEN")
    result = f"# {owner}/{repo_name}のディスカッション\n"
    # GraphQLクエリ
    query = """
    {
    repository(owner: "%s", name: "%s") {
        discussions(first: 100) {
        nodes {
            id
            title
            url
            bodyText
        }
        }
    }
    }
    """ % (
        owner,
        repo_name,
    )

    headers = {
        "Authorization": f"bearer {github_token}",
        "Content-Type": "application/json",
    }

    # リクエスト送信
    response = requests.post(
        "https://api.github.com/graphql", json={"query": query}, headers=headers
    )

    for discussion in response.json()["data"]["repository"]["discussions"]["nodes"]:
        result += f"## {discussion['title']}\n**URL**\n - {discussion['url']}\n**内容**\n{discussion['bodyText']}\n"

    # 結果を表示
    return result


if __name__ == "__main__":
    print(run("https://github.com/openai/openai-python"))
