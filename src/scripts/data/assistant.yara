rule open_notion_url
{
    strings:
        $url = "http"
        $scheme = "://"
        $domain = "notion.so"
    condition:
        ($url and $scheme and $domain)
}

rule open_slack_url
{
    strings:
        $url = "http"
        $scheme = "://"
        $domain = "slack.com/archives"
    condition:
        ($url and $scheme and $domain)
}

rule open_slack_canvas_url
{
    strings:
        $url = "http"
        $scheme = "://"
        $domain = "slack.com/canvas"
    condition:
        ($url and $scheme and $domain)
}

rule open_github_url
{
    strings:
        $url = "http"
        $scheme = "://"
        $domain = "github.com"
    condition:
        ($url and $scheme and $domain)
}

rule open_youtube_url
{
    strings:
        $url = "http"
        $scheme = "://"
        $domain1 = "youtu.be"
        $domain2 = "youtube.com"
    condition:
        ($url and $scheme) and ($domain1 or $domain2)
}

rule open_url
{
    strings:
        $url = "http"
        $scheme = "://"
        $ignore_url1 = "slack.com"
        $ignore_url2 = "notion.so"
        $ignore_url3 = "youtube.com"
        $ignore_url4 = "drive.google.com"
        $ignore_url5 = "youtu.be"
    condition:
        ($url and $scheme) and not ($ignore_url1 or $ignore_url2 or $ignore_url3 or $ignore_url4 or $ignore_url5)
}

rule knowledge_search
{
    strings:
        $source = /slack|notion|github/i
        $knowledge = "ナレッジ"
        $investigate1 = "調査して"
        $investigate2 = "調べ"
        $find = "探して"
        $search = "検索"
    condition:
        ($knowledge or $source) and ($search or $find or $investigate1 or $investigate2)
}

rule google_search
{
    strings:
        $google = /google/i
        $internet = "インターネット"
        $investigate1 = "調査して"
        $investigate2 = "調べ"
        $find = "探して"
        $search = "検索"
    condition:
        ($google or $internet) and ($search or $find or $investigate1 or $investigate2)
}

rule fact_checker
{
    strings:
        $keyword1 = "ファクトチェック"
    condition:
        $keyword1
}

rule intelx_search
{
    strings:
        $keyword1 = "脅威情報"
        $keyword2 = "情報漏洩"
        $keyword3 = "調査"
        $keyword4 = "調べて"
    condition:
        ($keyword1 or $keyword2) and ($keyword3 or $keyword4)
}

rule python_coder
{
    strings:
        $keyword1 = /python/i
        $keyword2 = "実装"
        $keyword3 = "書いて"
        $keyword4 = "教えて"
    condition:
        $keyword1 and ($keyword2 or $keyword3 or $keyword4)
}

rule public_data
{
    strings:
        $public = "パブリック"
        $data = "データ"
    condition:
        ($public and $data)
}

rule get_github_discussion
{
    strings:
        $keyword1 = "ディスカッション"
        $keyword2 = "github.com/"
    condition:
        ($keyword1 and $keyword2)
}

rule public_api
{
    strings:
        $public = "パブリック"
        $api = /API/i
    condition:
        ($public and $api)
}
rule pptx_writer
{
    strings:
        $keyword1 = /pptx/i
        $keyword2 = "パワーポイント"
        $keyword3 = "書いて"
        $keyword4 = "出力して"
    condition:
        ($keyword1 or $keyword2) and ($keyword3 or $keyword4)
}