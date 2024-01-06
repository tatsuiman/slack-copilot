import os
import json
import logging
import requests

API_KEY = os.getenv("GOOGLE_SEARCH_API_KEY")


def run(query: str) -> str:
    url = "https://factchecktools.googleapis.com/v1alpha1/claims:search"
    params = {"key": API_KEY, "query": query, "languageCode": "en"}
    resp = ""

    response = requests.get(url, params=params)
    results = response.json()
    if response.status_code == 200:
        if results.get("claims"):
            for claim in results["claims"]:
                resp += f"主張: {claim['text']}\n"
                resp += f"主張者: {claim.get('claimant', '情報なし')}\n"
                resp += f"主張日: {claim.get('claimDate', '情報なし')}\n"
                resp += "ファクトチェック情報:\n"
                for review in claim.get("claimReview", []):
                    resp += f"  - 出版社: {review['publisher']['name']}\n"
                    resp += f"  - レビューURL: {review['url']}\n"
                    resp += f"  - レビュータイトル: {review.get('title')}\n"
                    resp += f"  - レビュー評価: {review.get('textualRating')}\n"
                    resp += "\n"
            return resp
        else:
            return "ファクトチェックの結果を取得できませんでした。"
    else:
        return f"APIエラーが発生しました。({results})"


if __name__ == "__main__":
    query = "bill gates conspiracy theory"
    print(run(query))
