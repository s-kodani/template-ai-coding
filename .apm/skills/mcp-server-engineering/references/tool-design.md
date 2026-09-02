# Tool Design

このreferenceはTool境界、description、input/output schema、LLM usabilityを設計・レビューするときに読む。

## 1. ToolはLLM向けInterfaceである

Tool definitionを単なるAPI bindingとして扱わない。

```text
Tool name             → どのToolを選ぶか
Tool description      → いつ使うか / 何ができるか
inputSchema           → どう呼び出すか
property.description  → 各argumentに何を入れるか
outputSchema          → 結果をどう解釈するか
```

LLMが推測しなければ使えないToolは未完成とみなす。

## 2. Tool Boundary

可能な限り1つの明確なActionを1 Toolにする。

推奨:

```text
get_customer
search_customers
create_customer
update_customer
delete_customer
```

避ける:

```text
manage_customer(action: "get" | "create" | "delete")
```

ただし操作面が非常に大きいAPIでは、Tool catalog肥大化を避けるため `search/discover + execute` patternを検討する。

## 3. Read / Write Separation

Read、Mutation、Destructive operationを不用意に混在させない。
特に削除・停止・送金・公開・権限変更などは独立Toolにする。

Tool annotationはUX hintでありSecurity boundaryではない。
AuthorizationはServer-sideで行う。

## 4. Tool Name

Tool名は以下を満たす。

- Actionが分かる
- 一意
- 短い
- 安定している
- sibling Toolと区別できる

避ける: `manage`, `execute`, `api`, `do_it` のような曖昧な名前。

## 5. Tool Description

Descriptionは「何をするか」だけでなく、誤選択を防ぐ契約として書く。

必要に応じて以下を含める。

- 何をするToolか
- 何を返すか
- いつ使うか
- 何をしないか
- sibling Toolとの使い分け
- 重要な副作用
- 重要な前提条件

悪い例:

```text
Searches for issues.
```

良い例:

```text
Issueのtitleとbodyをkeyword検索する。commentとPull Requestは検索しない。
emailからUserを探す場合は別Toolを使う。
```

DescriptionをPrompt Injectionに利用しない。

## 6. Input Schema

ToolsはJSON Schema 2020-12で表現可能な制約をSchemaに定義する。

積極的に利用する。

- required
- enum
- minLength / maxLength
- minimum / maximum
- format
- pattern
- additionalProperties
- nested object
- array constraints
- oneOf / anyOf / dependent rules（必要な場合）

機械的に表現可能な制約をdescriptionだけに書かない。

```text
Machine-enforceable constraint → JSON Schema
Semantic meaning / usage guidance → description
```

Schema validationがあってもApplication-level validationを省略しない。

## 7. Property Description

`inputSchema.properties.*` には、型とparameter名だけで意味が完全に明白な場合を除き、原則 `description` を付与する。

Descriptionは人間向け文書だけでなく、LLMが正しいargumentを生成するためのInterface metadataとして扱う。

必要に応じて以下を書く。

- parameterが何を表すか
- 指定すべき値
- identifierの種類
- 値の単位
- format
- timezone
- inclusive / exclusive
- 省略時の挙動
- 特殊値の意味
- 他parameterとの関係
- 使用してはいけない値

### Identifier

悪い例:

```json
{
  "id": {
    "type": "string",
    "description": "ID"
  }
}
```

良い例:

```json
{
  "orderId": {
    "type": "string",
    "description": "注文を一意に識別するAPI内部のorder ID。表示用の注文番号ではない。"
  }
}
```

### Date / Time

最低限format、timezone、境界の意味を明確にする。

```json
{
  "createdAfter": {
    "type": "string",
    "format": "date-time",
    "description": "この日時以降に作成されたレコードを対象とする。RFC 3339形式のUTC日時を指定し、指定時刻自身を含む。"
  }
}
```

### Units

数値の単位を曖昧にしない。可能ならparameter名にも単位を入れる。

```json
{
  "timeoutMs": {
    "type": "integer",
    "minimum": 100,
    "maximum": 30000,
    "description": "Upstream requestのタイムアウト時間をミリ秒単位で指定する。"
  }
}
```

### Boolean

`true` / `false` の副作用を明示する。

```json
{
  "force": {
    "type": "boolean",
    "default": false,
    "description": "trueの場合、依存関係の警告があっても削除を続行する。通常はfalseのまま使用する。"
  }
}
```

### Enum

値の意味が名称だけで明白でない場合は説明する。

```json
{
  "status": {
    "type": "string",
    "enum": ["active", "suspended", "closed"],
    "description": "対象状態。active=利用可能、suspended=一時停止、closed=解約済み。"
  }
}
```

### Cross-field Constraint

Schemaで可能な限り表現し、LLMに理解しづらい関係はdescriptionでも補足する。

## 8. Description Quality Gate

各parameterについて確認する。

- 名前だけで意味を誤解しないか
- identifierの種類が分かるか
- 単位が分かるか
- format / timezoneが分かるか
- default behaviorが分かるか
- boundaryがSchemaに定義されているか
- enumの意味が分かるか
- 他parameterとの関係が分かるか
- LLMへの不要な命令が含まれていないか

## 9. Output Schema

機械利用される結果には可能な限りstructured outputと`outputSchema`を使う。

例:

```json
{
  "items": [],
  "nextCursor": null
}
```

Human-readable textだけに依存しない。

大量一覧はPaginationを設計する。
必要ならcursor、limit、nextCursorを使い、Server-side upper boundを設定する。

## 10. Determinism

同じ権限・同じServer状態ならTool listやSchemaの順序を決定論的にする。
Client cache、prompt cache、test reproducibilityを損なうランダム生成を避ける。

## 11. Error Design

Protocol ErrorとTool Execution Errorを区別する。

Tool Execution Errorでは、モデルが回復できる場合に以下を返す。

- 何が失敗したか
- なぜ失敗したか
- どう修正できるか

Secret、不要なPII、内部stack traceを返さない。
