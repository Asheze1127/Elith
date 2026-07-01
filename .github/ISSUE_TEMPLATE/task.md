---
name: タスク
about: 1つの目的に絞った実装タスク（1 Issue = 1 PR = 1目的）
title: "[FE|BE|INFRA-NN] <短いタイトル>"
labels: []
---

## 目的

<このタスクで何を達成するか。1〜2行>

## 完了条件（Definition of Done）

- [ ] <満たすべき具体的な条件>
- [ ] 変更領域のテスト・リンタが通る
- [ ] 例外系でユーザに分かるメッセージが返る

## レビュー観点

<レビュアーが特に見るべき点。なければ「特になし」>

## 依存関係（レビュー順の根拠）

- **Depends on**: #<前提となるIssue。これがマージ済みであること> <!-- 無ければ「なし」 -->
- **Blocks**: #<このIssueが終わらないと進めないIssue>

## メタ

- レイヤ: `frontend` / `backend` / `infra`
- フェーズ: `Phase 0` / `Phase 1` / `Phase 2` / `Phase 3`
- 関連docs: `docs/details/<file>.md`
