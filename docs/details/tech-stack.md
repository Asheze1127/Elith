# 技術スタック

採用技術と採用理由。技術選定そのものより、**RAGとして成立する構造**と**設定で差分を吸収できる構造**を支えることを優先する。

---

## 0. 前提定義（最初に決める）

| 項目 | 内容 |
|---|---|
| アプリ形態 | Web アプリ（Next.js + FastAPI の2サービス） |
| デプロイ想定 | GCP Cloud Run（実デプロイは必須でない。READMEに想定構成を記載） |
| ローカル動作 | docker-compose（web / api / db）。サンプルデータで確認可 |
| LLM/Embedding | Provider 抽象化。`ENVIRONMENT=local` のとき **Gemini 無料API**（費用ゼロ）、APIキー無し時は mock にフォールバック。本番はキーを Secret Manager 経由で注入 |
| IaC | Terraform（**想定構成の記述用**。今回は適用しない＝デプロイしない） |

---

## 1. 技術スタック構成

Next.js（フロント）→ FastAPI（バック）→ PostgreSQL + pgvector（リレーショナル + ベクトルを単一ストアに集約）。LLM/Embedding は Provider インターフェースで抽象化。

---

## 2. フロントエンド

| 項目 | 採用技術 | 採用理由 | 備考 |
|---|---|---|---|
| 言語 | TypeScript | 型でAPI境界を固める | |
| フレームワーク | Next.js（App Router） | チャットUIを薄く素早く構築 | 凝りすぎず中身(RAG)に集中 |
| UI | （任意）Tailwind / shadcn/ui | 最小のチャット画面 | |
| 状態管理 | React state / SWR or fetch | `GET /tenant/config` を取得しUI駆動 | テナント別コンポーネントは作らない |
| テスト | Vitest / Playwright（任意） | 主要導線の確認 | |

---

## 3. バックエンド

| 項目 | 採用技術 | 採用理由 | 備考 |
|---|---|---|---|
| 言語 | Python | RAG周辺ライブラリが充実 | |
| 実行環境 | FastAPI + Uvicorn | `Depends` でテナントコンテキスト注入が綺麗 | コンテナ化しCloud Run想定 |
| 構成 | レイヤ分離（api / deps / rag / policies / providers / repository / models） | 共通パイプラインと差分(config)を分離 | `details/directory.md` |
| API方式 | REST（`/chat`, `/tenant/config`, `/documents`, `/feedback`） | シンプル | `/chat` は全テナント共通 |
| DBアクセス | SQLAlchemy 等 | すべて `tenant_id` スコープ | |
| 認証/テナント解決 | **セッション（ログイン）からtenant_idを取得** | `Depends`の入力源。認証IDから取るのでなりすまし耐性が高い。1URLでローカルも動く | `screen-flow.md` |

---

## 4. データベース

| 項目 | 採用技術 | 採用理由 | 備考 |
|---|---|---|---|
| 主DB | PostgreSQL | テナント/設定/回答/フィードバック等を一元管理 | |
| ベクトル検索 | **pgvector** | 専用ベクトルDBを足さず構成部品を最小化。Cloud SQLで完結 | チャンクの埋め込みを同居 |
| 検索方針 | 文書分割→埋め込み→近傍検索（+メタデータ絞り込み） | RAGの基本 | scope/カテゴリで絞り込み |

---

## 5. インフラ / DevOps

| 項目 | 採用技術 | 採用理由 | 備考 |
|---|---|---|---|
| ホスティング | GCP Cloud Run（web / api の2サービス） | コンテナを渡すだけ。HTTPS・LB・オートスケール・マルチゾーン込み、待機中は0台＝無料。K8s不要 | `infrastructure.md` |
| 生ファイル保存 | Cloud Storage（GCS） | アップロードされたPDF等の原本を保管（索引はpgvector側） | |
| データ | Cloud SQL（PostgreSQL + pgvector） | マネージドで運用簡素 | |
| 秘密情報 | Secret Manager | APIキー等をコードに入れない | |
| コンテナ | Docker / docker-compose（ローカル） | READMEの手順で再現可能 | |
| IaC | Terraform | 想定構成の記述用。**今回は適用しない（デプロイしない）** | |
| ログ | Cloud Logging | 回答評価ログ・改善候補の確認 | |
| CI/CD | （任意）GitHub Actions | テスト/リンタ | |

---

## 6. セキュリティ

| 項目 | 方針 | 評価観点 |
|---|---|---|
| テナント分離 | 全クエリを `tenant_id` でスコープ | 他テナントのデータに到達しないか |
| 回答モード | 社外/社内など出力制御を config で持つ | 社内専用情報が社外回答に漏れないか |
| 秘密情報 | Secret Manager / `.env`、コミットに含めない | トークン全文ログ出力をしない |
| 入力注意 | （C社想定）個人情報らしき入力に注意喚起 | PIIの扱い |
| 根拠の扱い | 根拠不足時は断定せず「確認が必要」 | 誤情報を断定しない |
