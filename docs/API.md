# Public API

この文書は、ShellgeiOnlineJudgeの外部公開HTTP API contractの正本です。
request bodyや接続の制限は
[セキュリティモデルと制約](../SECURITY.md#ネットワークとhttpの制約)、
問題ID・判定規則は[問題データ](../problems/README.md)を参照してください。

## v3 submission API

`POST /api/v3/submissions`へ`application/json`で次のbodyを送ります。

```json
{
  "shellgei": "printf ok",
  "problem_id": "STANDARD-00000001"
}
```

`shellgei`は1文字以上1,000文字以下のUTF-8文字列です。CRを除去するため、
CRLFはLFになり、単独のCRは削除されます。NULと不正Unicodeは拒否します。
`problem_id`は1文字以上64文字以下で、
ASCII英数字をhyphenで区切った形式だけを受け付けます。未知fieldは拒否します。

検証済みの実行結果と判定結果を取得できた場合は、正解・不正解・実行失敗にかかわらず
HTTP 200で次の型付きresponseを返します。受付拒否やrunner応答を取得・検証できない
場合の扱いは[HTTP statusとerror](#http-statusとerror)を参照してください。

```json
{
  "api_version": 3,
  "submission_id": 42,
  "submitted_at": "2026-09-02T12:34:56+09:00",
  "verdict": "accepted",
  "reason": null,
  "execution": {
    "status": "completed",
    "stdout": "ok",
    "stderr": "",
    "exit_code": 0,
    "timed_out": false,
    "truncated": false,
    "duration_ms": 12
  },
  "artifact": null,
  "persistence": "saved"
}
```

主なfieldは次の意味です。

| Field | Type | Meaning |
| --- | --- | --- |
| `api_version` | `3` | public response schema version |
| `submission_id` | positive integer / `null` | 保存済み実行ログID。DB保存不能時は`null` |
| `submitted_at` | timezone付きRFC 3339 datetime | serviceが提出を受け付けた時刻 |
| `verdict` | enum | 判定結果 |
| `reason` | enum / `null` | 不正解・実行失敗・判定失敗の安全な理由 |
| `execution` | object | 分離出力、終了code、制限状態、実行時間 |
| `artifact` | object / `null` | 画像のMIMEとBase64 data |
| `persistence` | `saved` / `unavailable` | 実行ログ保存状態 |

`execution.status`は`completed`、`timed_out`、`output_limit`、`error`のいずれかです。
内部Docker errorの文字列は公開しません。`stdout`と`stderr`の合計は1,000文字以下です。

`verdict`は次のいずれかです。

- `accepted`
- `wrong_answer`
- `wrong_image`
- `wrong_text_and_image`
- `execution_failure`
- `judge_error`

`reason`は`output_mismatch`、`image_mismatch`、`output_and_image_mismatch`、
`artifact_missing`、`artifact_path_mismatch`、`artifact_media_type_mismatch`、
`artifact_invalid`、`non_zero_exit`、`stderr_not_empty`、`timed_out`、
`output_truncated`、`execution_error`、`invalid_problem_id`、`problem_not_found`の
いずれか、または理由がない場合の`null`です。

画像artifactは`media_type`と`data`だけを返します。MIMEは`image/jpeg`または
`image/gif`、Base64 dataは1,000,000文字以下です。runner内部の取得pathは公開しません。
HTTP 200のresponse全体は1,025,000 bytes以下です。

## HTTP statusとerror

404・429・503は、内部例外やcommandを含まない固定のerrorを返します。
422はFastAPIの標準validation error形式で、`detail`に拒否した入力値を含む場合があります。

| Status | `code` | Meaning |
| --- | --- | --- |
| 404 | `problem_not_found` | 登録されていないproblem ID |
| 422 | FastAPI validation error | request schema違反 |
| 429 | `runner_busy` | runnerの受付容量超過 |
| 503 | `runner_unavailable` | runner停止または検証済み応答を取得不能 |

404、429、503のbodyは次の形式です。429と503には`Retry-After: 1`も付与します。

```json
{
  "api_version": 3,
  "code": "runner_busy",
  "message": "Runner capacity is temporarily exhausted"
}
```

提出requestとresponseには利用者のcommand・出力を含むため、backendが返す
200・404・422・429・503には`Cache-Control: no-store`と
`X-Content-Type-Options: nosniff`を付与します。

これらの提出responseに、backendがリクエストごとに生成した
128-bitの小文字16進数`X-Request-ID`を付与します。browserからも読めるよう
CORSのexpose headerに含めます。clientが送信した`X-Request-ID`は信頼・再利用せず、
必ずserver側で新しい値へ置き換えます。問い合わせ時には、responseのこの値を
対象requestの特定に使用できます。

予期しない未処理例外による500や、前段proxyが生成する応答は、上記のtyped error形式と
header付与の保証対象外です。

## legacy submission API

外部clientの移行互換性のため、`POST /api/shellgei`も維持しています。
requestは同じ`ShellgeiData`形式で、responseは`output`、文字列の`id`、JSTの`date`、
Base64 `image`、`image_media_type`、数字文字列の`judge`を返します。

legacy APIではrunner混雑・停止もHTTP 200と`judge: "4"`へ変換します。
未登録problemは404、request schema違反は422です。

- `id`はDB保存不能時やrunner混雑・停止時に`"-1"`となる。DB保存不能時も実行・判定結果は返す
- 画像がない場合は`image: ""`、`image_media_type: null`を返す
- `judge`は`accepted`を`"1"`、`wrong_image`を`"2"`、`wrong_answer`を`"3"`へ変換し、
  `wrong_text_and_image`・`execution_failure`・`judge_error`を`"4"`へまとめる

新規clientは、
HTTP status、typed verdict、分離出力を利用できるv3 APIを使用してください。
標準frontendもv3 APIを使用し、受信JSONを実行時に検証してから表示へ変換します。
legacy APIの200・404・422にも`Cache-Control: no-store`と
`X-Content-Type-Options: nosniff`を付与します。`X-Request-ID`の生成・応答規則と
未処理例外・前段proxyの制約もv3 APIと同じです。

## problem API

問題一覧`GET /api/problems`は、`id`、`category`、`title_ja`、`title_en`を持つ配列を
返します。問題詳細`GET /api/problems/{problem_id}`は、`title_ja`、`statement_ja`、
`title_en`、`statement_en`、`input`、`expected_output`、`answer`、`image`を返します。
各fieldは文字列です。`answer`はschema v3の`reference_solution`を公開する参照解答で、
現在のfrontendの問題表示には使用しません。`input`は`input.txt` fixtureの内容、
`image`は全問題で表示用JPEGの相対URLです。
これらは現在versionなしの互換endpointです。frontendのAPI clientは受信した全表示fieldを
実行時に型検証します。将来versioningする場合は、既存endpointの互換性と移行期間を
別途定義します。
