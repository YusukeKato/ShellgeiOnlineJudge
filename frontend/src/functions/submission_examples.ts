export interface SubmissionExampleProps {
  sojUrl: string;
  shellgei: string;
  problemId: string;
}

function exampleValues({ sojUrl, shellgei, problemId }: SubmissionExampleProps) {
  // 画面と同じ送信先・現在の入力を使い、空欄だけをサンプルで補う。
  return {
    endpoint: `${(sojUrl || window.location.origin).replace(/\/+$/, "")}/api/v3/submissions`,
    payload: { shellgei: shellgei || "printf '%s\\n' 'test'", problem_id: problemId },
  };
}

export function buildCurlCommand(props: SubmissionExampleProps): string {
  // JSON本文とshellのURL引用を別々に処理し、入力を端末側で展開させず送れる例を返す。
  // 改行もJSON内でescapeするため、入力中のJSON行がheredocの終端にはならない。
  const { endpoint, payload } = exampleValues(props);
  const quotedUrl = `'${endpoint.replaceAll("'", "'\\''")}'`;
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
