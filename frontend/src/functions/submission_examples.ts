export interface SubmissionExampleProps {
  sojUrl: string;
  shellgei: string;
  problemId: string;
}

function apiBaseUrl(sojUrl: string): string {
  // 取得例と提出例で同じAPIのorigin・path prefixを使い、末尾のslashだけを除く。
  return (sojUrl || window.location.origin).replace(/\/+$/, "");
}

function quoteShell(value: string): string {
  // URLをshellの単一引数として引用し、端末上の展開やcommand置換を防ぐ。
  return `'${value.replaceAll("'", "'\\''")}'`;
}

export function buildCurlProblemCommands(props: SubmissionExampleProps): string {
  // 一覧と選択中の詳細をGETする例を返す。問題IDはpath要素としてencodeする。
  const url = `${apiBaseUrl(props.sojUrl)}/api/problems`;
  return `# List problems (IDs and titles)
curl --fail --show-error --max-time 30 ${quoteShell(url)}

# Get the selected problem (statement, input, expected output and example answer)
curl --fail --show-error --max-time 30 ${quoteShell(`${url}/${encodeURIComponent(props.problemId)}`)}
`;
}

export function buildPythonProblemScript(props: SubmissionExampleProps): string {
  // 標準libraryだけで問題dataを取得・表示する。解答の実行・提出やfile保存は行わない。
  const url = `${apiBaseUrl(props.sojUrl)}/api/problems`;
  return `import json
from urllib.parse import quote
from urllib.request import urlopen

url = ${JSON.stringify(url)}
problem_id = ${JSON.stringify(props.problemId)}

with urlopen(url, timeout=30) as response:
    problems = json.load(response)
for problem in problems:
    print(problem["id"], problem["title_ja"], problem["title_en"])

with urlopen(url + "/" + quote(problem_id, safe=""), timeout=30) as response:
    detail = json.load(response)
print(json.dumps(detail, ensure_ascii=False, indent=2))
`;
}

function exampleValues({ sojUrl, shellgei, problemId }: SubmissionExampleProps) {
  // 画面と同じ送信先・現在の入力を使い、空欄だけをサンプルで補う。
  return {
    endpoint: `${apiBaseUrl(sojUrl)}/api/v3/submissions`,
    payload: { shellgei: shellgei || "printf '%s\\n' 'test'", problem_id: problemId },
  };
}

export function buildCurlCommand(props: SubmissionExampleProps): string {
  // JSON本文とshellのURL引用を別々に処理し、入力を端末側で展開させず送れる例を返す。
  // 改行もJSON内でescapeするため、入力中のJSON行がheredocの終端にはならない。
  const { endpoint, payload } = exampleValues(props);
  const quotedUrl = quoteShell(endpoint);
  return `curl ${quotedUrl} \\
  -H 'Content-Type: application/json' \\
  --data-binary @- <<'JSON'
${JSON.stringify(payload)}
JSON
`;
}

export function buildPythonScript(props: SubmissionExampleProps): string {
  // 文字列をPythonでも有効な引用形式へ変換し、標準libraryだけの送信・JSON読取例を返す。
  // 利用者commandをPythonコードやローカルshellとして評価せず、送信dataにだけ含める。
  const { endpoint, payload } = exampleValues(props);
  return `import json
from urllib.request import Request, urlopen

url = ${JSON.stringify(endpoint)}
payload = {
    "shellgei": ${JSON.stringify(payload.shellgei)},
    "problem_id": ${JSON.stringify(payload.problem_id)},
}
request = Request(
    url,
    data=json.dumps(payload).encode("utf-8"),
    headers={"Content-Type": "application/json"},
)

with urlopen(request, timeout=30) as response:
    result = json.load(response)

print("verdict:", result["verdict"])
print("stdout:", repr(result["execution"]["stdout"]))
print("stderr:", repr(result["execution"]["stderr"]))
`;
}
