# 概要
ナレッジ管理に特化したSlackで動作するChatGPTです。

## Features

- [x] Assistant APIを利用したslack専用チャットbot
- [x] スレッドやcanvas、アップロードしたファイルを文脈として自動入力
- [x] notion github google driveなどナレッジの検索が可能
- [x] APIクレジットを無駄遣いしないように練習モードを搭載
- [ ] ユーザの発言を学習することで、より自然な発言を行うことが可能

## アーキテクチャ
![アーキテクチャ](docs/diagram.png)

## 動作フロー
Events API
```mermaid
sequenceDiagram
    participant Slack
    participant Callback as handler<br/>(Lambda)
    participant Assistant as Processor<br/>(Lambda)
    participant DynamoDB
    participant OpenAI as OpenAI<br/>AssistantsAPI

    Slack->>Callback: メッセージ
    Callback-->>Assistant: SNS経由で呼び出し (非同期)
    Callback->>Slack: status: 200 (3秒以内)
    Assistant->>DynamoDB: スレッドID取得
    opt スレッドIDが存在しない場合
        Assistant->>OpenAI: 新規スレッド生成
        Assistant->>DynamoDB: スレッドID保存
    end
    Assistant->>OpenAI: スレッドが実行中か確認
    opt スレッドが実行中の場合
        Assistant-->>Slack: エラーメッセージ返却
    end
    opt ファイルがある場合
        Assistant->>Slack: ファイルダウンロード (SlackAPI)
        Assistant->>OpenAI: ファイルアップロード
    end
    Assistant->>OpenAI: スレッドにメッセージ追加
    Assistant->>DynamoDB: アシスタントの設定を取得
		Assistant ->> OpenAI: アシスタントの設定を更新
    Assistant->>OpenAI: スレッドを実行 (Run)
    loop StreamingAPIを使ってメッセージを非同期で受信する
        opt 回答の生成結果が通知される場合
		        OpenAI -->> Assistant: 生成された文字列を通知
            Assistant-->>Slack: メッセージを送信または編集
        end
        opt function_callが必要な場合
		        OpenAI -->> Assistant: 関数名と引数を通知
            Assistant-->>OpenAI: 関数の実行結果を返却
        end
        opt ファイルの生成結果が通知される場合
		        Assistant -->> OpenAI: ファイルのリクエスト
		        OpenAI -->> Assistant: ファイルをダウンロード
            Assistant-->>Slack: ファイルを送信
				end
        opt 生成結果を受信する場合<br>(compleated,failed, cancelled, expired)
            Assistant-->>Slack: 結果を返却
        end
    end
```

ショートカットコマンド
```mermaid
sequenceDiagram
    participant Slack as Slack
    participant Assistant as handler<br/>(Lambda)
    participant DynamoDB as DynamoDB

    Slack->>Assistant: ショートカットを起動する
    Assistant -->> Slack: モーダルを表示
    Slack ->> Assistant: モーダル経由でアシスタント名を受け取る
    Assistant ->> Assistant: アシスタント名から設定を取得
    Assistant->>DynamoDB: 設定を保存
```

## Functions
以下はチャットボットが呼び出し可能な機能一覧です。
独自のfunctionの実装方法は[こちら](./src/scripts/functions/README.md)

- `create_notion_page`: 指定されたタイトルと内容でNotionページを作成します。
- `open_youtube_url`: YoutubeのURLから字幕を取得します。
- `open_slack_url`: SlackのURLからスレッドのメッセージ一覧を取得します。
- `open_notion_url`: NotionAPIを利用してしページの内容を取得します。
- `open_url`: 指定されたURLを開き、その内容を取得します。ウェブページのスクレイピングやAPIのレスポンス取得に使用されます。
- `open_slack_canvas_url`: slack canvas urlからコンテンツを取得します。
- `google_search`: Googleのカスタム検索エンジンを利用して、ウェブ全体から情報を検索します。特定のキーワードに基づいた検索結果を返します。
- `google_drive_search`: Google Driveからファイル名を検索することができます。キーワードに基づいた検索結果を返します。
- `slack_search`: SlackのAPIを利用して、特定のチャンネルやユーザーのメッセージ履歴を検索します。
- `notion_search`: NotionのAPIを利用して、Notion内のページやデータベースを検索します。
- `github_search`: GitHub内でのIssue、Pull Request、コードの検索を行い、結果を返します。
- `get_github_discussion`: Github DiscussionのURLからディスカッション一覧を取得することができます。
- `fact_checker`: GoogleのFact Check Tools APIを利用して、特定の主張やニュースの真偽を調査します。
- `intelx_search`: Intelligence XのAPIを利用して、様々なデータソース（ウェブページ、フォーラム、ドキュメントなど）から情報を検索します。

## Demo
### 1. CSVファイルの分析
![](docs/analysis.gif)
### 2. Notion検索
![](docs/notion_search.gif)
### 3. Github検索
![](docs/github_search.gif)
### 4. アシスタントの変更
![](docs/assistant.gif)
### 5. インシデント対応
![](docs/demo.gif)
### 6. Unfurl
![](docs/unfurl.gif)

## セットアップ
```bash
cp env.sample .envrc
direnv allow
npm install -g serverless
serverless plugin install -n serverless-api-gateway-throttling
serverless plugin install -n serverless-prune-plugin
aws ecr-public get-login-password --region us-east-1 | docker login --username AWS --password-stdin public.ecr.aws
sls deploy
```

## APIs
* [OpenAI API](https://platform.openai.com/api-keys)
* [Google AI Studio](https://makersuite.google.com/app/apikey?hl=ja)
* [Fact Check API](https://console.cloud.google.com/marketplace/product/google/factchecktools.googleapis.com?q=search&referrer=search)
* [Google Drive API](https://console.cloud.google.com/marketplace/product/google/drive.googleapis.com?q=search&referrer=search)
* [Notion API](https://developers.notion.com/)
* [Intelligence X API](https://intelx.io/account?tab=developer)
* [Github アクセストークン](https://docs.github.com/ja/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens)

## 関連
* [Slack Botの種類と大まかな作り方](https://qiita.com/namutaka/items/233a83100c94af033575)
* [OpenAI Assistants API で Slack チャットボットを構築する](https://zenn.dev/taroshun32/articles/slack-chatbot-with-openai-asistant)
