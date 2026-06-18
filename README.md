# Mリーグ ドラフトダッシュボード

## セットアップ手順

### 1. GitHubにリポジトリを作成
1. [github.com](https://github.com) でアカウントを作成（または既存のアカウントにログイン）
2. 「New repository」でリポジトリを作成（例: `mleague-dashboard`）
3. このフォルダの全ファイルをアップロード

### 2. Vercelにデプロイ
1. [vercel.com](https://vercel.com) にGitHubアカウントでログイン
2. 「New Project」でGitHubリポジトリを選択
3. 設定はそのままで「Deploy」をクリック
4. 完成！URLを仲間に共有してください

### 3. ドラフトチームの設定
`public/data/draft.json` を編集してチーム名と選手名を入力してください：
```json
{
  "teams": [
    {
      "id": "team1",
      "name": "あなたのチーム名",
      "players": ["選手名A", "選手名B", "選手名C", "選手名D"]
    },
    ...
  ]
}
```
※ 選手名はMリーグ公式サイトの表記に合わせてください

### 4. 役満が出たとき
`public/data/yakuman.json` に追記してください：
```json
{
  "yakuman": [
    {
      "date": "2025-10-15",
      "player": "選手名",
      "yaku": "国士無双",
      "score": 32000
    }
  ]
}
```

## 自動スクレイピング
GitHub Actionsが毎日深夜0時（JST）に自動で試合結果を取得します。
手動で実行したい場合は、GitHubリポジトリの「Actions」タブから実行できます。

## フォルダ構成
```
mleague-dashboard/
├── .github/workflows/scrape.yml  # 自動実行設定
├── public/
│   ├── index.html                # ダッシュボード画面
│   ├── style.css
│   ├── app.js
│   ├── data/
│   │   ├── results.json          # 試合結果データ（自動更新）
│   │   ├── draft.json            # ドラフトチーム設定（手動編集）
│   │   └── yakuman.json          # 役満記録（手動編集）
│   └── images/players/           # 選手顔写真（自動取得）
├── scripts/
│   ├── scrape.py                 # スクレイピングスクリプト
│   └── requirements.txt
└── vercel.json
```
