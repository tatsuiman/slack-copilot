rule ask_slack_ai
{
    meta:
        message = "こんにちは。気軽に質問してください"
        description = "SlackでAIについて質問された場合に返信するルール"
    strings:
        $keyword1 = /slack/i
        $keyword2 = /ai/i
        $keyword3 = "教えて"
        $keyword4 = "使い方"
        $keyword5 = "知りたい"
        $keyword6 = "わからない"
    condition:
        ($keyword1 and $keyword2) and ($keyword3 or $keyword4 or $keyword5 or $keyword6)
}