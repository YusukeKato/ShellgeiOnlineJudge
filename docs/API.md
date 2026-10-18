# Public API

この文書は、ShellgeiOnlineJudgeの外部公開HTTP API contractの正本です。
起動・検査・変更の反映は[開発手順](./DEVELOPMENT.md)、内部runner protocolは
[backend文書](../backend/README.md#内部runner-protocol)を参照してください。

| clientの目的 | 使用するendpoint | 読む節 |
| --- | --- | --- |
| コマンドを提出し、実行・判定・保存状態を受け取る | `POST /api/v3/submissions` | [v3 submission API](#v3-submission-api)、[HTTP statusとerror](#http-statusとerror) |
| 問題一覧・詳細を取得する | `GET /api/problems`、`GET /api/problems/{problem_id}` | [problem API](#problem-api) |
| 既存clientを移行する | `POST /api/shellgei` | [legacy submission API](#legacy-submission-api) |

OpenAPIの`info.version`は[製品versionの正本](./RELEASE.md#バージョンの正本)に従います。
responseの`api_version: 3`はAPI互換性を表し、製品versionとは別です。
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

DB障害または保存受付枠が満杯の場合も、実行・判定済みならHTTP 200で結果を返し、
`submission_id: null`、`persistence: unavailable`とします。保存の自動再試行は行いません。
受付上限と保証範囲は[実行ログの制約](../SECURITY.md#実行ログとdockerログ)を参照してください。

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

全問題で`media/output.gif`に生成したGIFを表示できます。runnerは表示用GIFを
判定用artifactと別に回収します。backendの形式・全frame検証を通ったGIFがあれば
公開`artifact`に優先して返し、なければ従来の判定用画像（または`null`）を返します。
GIFは採点に使わず、画像問題でも定義された判定用画像だけで採点します。
壊れたGIF・画像上限超過は判定を変えず表示から除外し、timeout・出力超過・基盤errorでは
画像を返しません。GIFのframe・delay・loopは変換せず保持します。
回収path、共有byte枠、画素上限の正本は[SECURITY.md](../SECURITY.md#stdoutstderr画像)です。
legacy APIの`image`・`image_media_type`にも同じ選択規則を適用します。

## HTTP statusとerror

この節はv3提出APIの規則です。問題取得時のstatusとcacheは[problem API](#problem-api)を参照してください。

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

カテゴリの値は[問題データ仕様](../problems/README.md#schema-v3)を参照してください。
正規表現カテゴリ`REGEX`も同じ一覧・詳細・提出APIを使用します。カテゴリを固定列挙するclientは追加値への対応が必要です。

### 一覧と詳細のresponse

問題一覧`GET /api/problems`は、`id`、`category`、`title_ja`、`title_en`を持つ配列を
返します。問題詳細`GET /api/problems/{problem_id}`は、`title_ja`、`statement_ja`、
`title_en`、`statement_en`、`input`、`expected_output`、`answer`、`image`を返します。
各fieldは文字列です。`answer`はschema v3の`reference_solution`を公開する参照解答で、
現在のfrontendの問題表示には使用しません。`input`は`input.txt` fixtureの内容、
`image`は全問題で表示用JPEGの相対URLです。
これらは現在versionなしの互換endpointです。frontendのAPI clientは受信した全表示fieldを
実行時に型検証します。将来versioningする場合は、既存endpointの互換性と移行期間を
別途定義します。

### HTTP statusとcache

| Endpoint | Status | 応答 |
| --- | --- | --- |
| `GET /api/problems` | 200 | ID順の問題一覧配列。`Content-Type: application/json` |
| `GET /api/problems` | 304 | `If-None-Match`が現在のETagと一致。本文なし |
| `GET /api/problems/{problem_id}` | 200 | 問題詳細object |
| `GET /api/problems/{problem_id}` | 404 | 形式は有効だが未登録のID。`{"detail":"Problem not found"}` |
| `GET /api/problems/{problem_id}` | 422 | path parameterの形式・長さvalidation違反。FastAPI標準validation error |

詳細APIの`problem_id`も、提出APIと同じ1〜64文字のASCII英数字をhyphenで区切った形式です。
一覧の200と304には`Cache-Control: public, max-age=300`と`ETag`を付与します。
ETagは一覧response本文のSHA-256を二重引用符で囲んだ値です。
`If-None-Match`はカンマ区切りの各値の前後の空白を除去し、現在のETagとの完全一致で判定します。
一致しない場合やheaderがない場合は200と一覧本文を返します。

一覧本文とETagは起動時に検証済みの問題repositoryから生成します。
問題dataを変更した場合の検査・反映は[問題データの更新手順](../problems/README.md)に従ってください。
詳細APIには、この一覧用のETag・Cache-Controlを付与しません。
提出APIの`no-store`やv3 typed errorの形式を問題API全体の規則として扱わないでください。
