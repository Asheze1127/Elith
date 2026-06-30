# ディレクトリ構成

**テナント名のディレクトリは作らない。** 増えるのは `tenant_config` の行とサンプルデータ。コードは「能力のカタログ」をレイヤ別に育てる。

## ディレクトリ構成図

```
.
├── web/        # Next.js フロントエンド
├── backend/    # FastAPI バックエンド
└── docs/       # 設計ドキュメント
```

---

## 0. 設計前提

- Monorepo（web / backend を1リポジトリに）
- バックエンドはレイヤ分離：共通パイプライン（コード）と差分（config データ）を分ける
- 差分はディレクトリでなく `tenant_config` で表現する（`multi-tenant-design.md`）

---

## 1. 全体構成（Monorepo）

```
.
├── web/
├── backend/
├── docs/
├── docker-compose.yml      # web / api / db をローカル起動
└── README.md               # セットアップ / 設計判断 / GCP想定構成
```

---

## 2. フロントエンド構成テンプレ（Next.js / レイヤ分離）

責務でレイヤを分ける。テナント別コンポーネントは作らず、差分は `tenant_config` を context 経由で受けて条件付きレンダリングする。

```
web/
├── app/                          # ルーティングとページ構成のみ（薄く保つ）
│   ├── layout.tsx                # Providers を差し込む
│   ├── providers.tsx             # TenantConfigProvider 等の client context
│   ├── page.tsx                  # / チャット（Container を mount するだけ）
│   ├── documents/page.tsx
│   └── review/page.tsx
│
├── components/
│   ├── presentational/           # 状態を持たず props で描くだけ（dumb）
│   │   ├── Button.tsx
│   │   ├── Badge.tsx             # ステータス表示の素
│   │   ├── Banner.tsx            # 警告表示の素
│   │   ├── Toggle.tsx
│   │   └── Spinner.tsx
│   └── container/                # hooks/api/config を束ね状態を持つ（smart）
│       ├── ChatContainer.tsx
│       ├── CitationPanel.tsx
│       ├── WarningList.tsx
│       ├── ModeToggle.tsx
│       └── FeedbackButtons.tsx
│
├── hooks/                        # 再利用ロジック
│   ├── useChat.ts
│   ├── useTenantConfig.ts        # context から config を読む
│   └── useFeedback.ts
│
├── lib/
│   ├── api/                      # fetch をここに閉じ込める（唯一の通信層）
│   │   ├── client.ts             # baseURL / 共通エラー処理 / ヘッダ
│   │   ├── chat.ts               # postChat()
│   │   ├── tenant.ts             # getTenantConfig()
│   │   ├── documents.ts
│   │   └── feedback.ts
│   └── utils/                    # 純粋関数（フォーマッタ等）
│       └── format.ts
│
├── context/
│   └── TenantConfigContext.tsx   # GET /tenant/config を保持しUI全体へ供給
│
├── types/                        # 型定義（バックエンドDTOと対応）
│   ├── tenant-config.ts          # TenantConfig
│   ├── chat.ts                   # Answer / Citation / Status / Warning
│   └── api.ts
│
└── package.json
```

> レイヤの責務：`app/`=ルーティングのみ / `components/presentational`=dumb（props描画）/ `components/container`=smart（hooks+api+config を束ねる）/ `hooks`=ロジック再利用 / `lib/api`=通信を一箇所に閉じ込め、コンポーネントから直接 fetch しない / `context`=config駆動レンダリングの供給源 / `types`=DTO型。
> container/presentational の2層構成。feature-first は採らない。

---

## 3. バックエンド構成テンプレ（FastAPI / レイヤ分離）

```
backend/
├── app/
│   ├── main.py             # FastAPI entrypoint
│   ├── api/                # ルーティング（全テナント共通）
│   │   ├── chat.py         # POST /chat
│   │   ├── tenant.py       # GET /tenant/config
│   │   ├── documents.py    # ドキュメント取り込み/一覧
│   │   └── feedback.py     # 回答フィードバック
│   ├── deps/               # Depends（横断的な注入）
│   │   └── tenant.py       # get_tenant_context / get_tenant_config
│   ├── rag/                # 共通RAGパイプライン
│   │   ├── pipeline.py     # オーケストレータ（config.pipeline を回す）
│   │   ├── retrieve.py     # tenant_id スコープの近傍検索
│   │   ├── prompt.py       # config を回答方針に反映
│   │   └── steps/          # 名前付き部品（共通カタログ）
│   │       ├── stale_warning.py
│   │       ├── contradiction_check.py
│   │       ├── ground_check.py
│   │       └── cite.py
│   ├── policies/           # 名前付きストラテジのレジストリ（bespoke含む）
│   │   └── registry.py
│   ├── providers/          # LLM / Embedding 抽象（ENVIRONMENT で切替）
│   │   ├── base.py         # interface
│   │   ├── gemini.py       # ENVIRONMENT=local：Gemini 無料API
│   │   └── mock.py         # APIキー無し時のフォールバック
│   ├── repository/         # データアクセス（すべて tenant_id スコープ）
│   ├── models/             # tenant, tenant_config, document, chunk, answer, citation, feedback
│   └── core/               # .env 読込, DB接続, logging
├── ingestion/             # 文書分割・埋め込み・索引化
├── sample_data/           # 動作確認用サンプル（A社想定）
└── tests/
```

> 🚫 `backend/app/tenants/a_sha/` のような **テナント別ディレクトリは作らない**。差分は `tenant_config`、bespoke ロジックは `policies/registry.py` に名前付きで登録する。

---

## 4. データモデル（境界設計）

課題要件「顧客・ワークスペース・ドキュメント・回答・引用の境界」を `models/` で表現する。

```
tenant ──< workspace ──< document ──< chunk(embedding)
tenant ──< tenant_config
answer ──< citation        # 回答とその根拠の境界
answer ──< feedback        # 改善候補の蓄積
```

---

## 5. インフラ構成

```
infra/
├── Dockerfile.web
├── Dockerfile.api
└── terraform/              # GCP想定構成の記述用（適用しない＝デプロイしない）
```

> Terraform は「READMEのGCP想定構成」を裏付けるための記述で、実デプロイはしない。**現時点では未作成**（設計確定後に書く）。

---

## 6. テスト構成テンプレ

```
backend/tests/
├── test_pipeline.py        # config 違いで振る舞いが変わることを検証
├── test_steps/             # 各共通部品の単体テスト
└── test_tenant_scope.py    # 他テナントのデータに到達しないこと
```
