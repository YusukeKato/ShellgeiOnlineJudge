import requests
import time
import os
from pathlib import Path


# .envファイルからサーバURLを取得
env_path = Path(__file__).resolve().parent.parent / ".env"
if env_path.exists():
    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            # 空行とコメントを除外
            if line and not line.startswith("#"):
                key, value = line.split("=", 1)
                os.environ.setdefault(key, value)
server_url = os.environ.get("SERVER_URL", "http://localhost:8000")
print(f"start test: {server_url}")

# APIエンドポイントのURL
api_shellgei_url = f"{server_url}/api/shellgei"
api_problems_url = f"{server_url}/api/problems"

# テスト処理
def test_func(shellgei, problem_id, is_correct):
    time.sleep(0.5)
    data = {
        "shellgei": shellgei,
        "problem_id": problem_id,
    }
    try:
        response = requests.post(url=api_shellgei_url, json=data)
    except requests.exceptions.RequestException as e:
        print(f"Request Error: {e}")
        assert False, "API request failed"
    print(f"{problem_id}\ninput: {shellgei}")
    if response.status_code == 200:
        res_json = response.json()
        print(f"output: {res_json.get('output', '')}")
        print("Status 200: OK")
        judge = res_json.get("judge", "").replace("\n", "")
        if judge == "1":
            print("Correct!!")
        else:
            print(f"Incorrect...({judge})")
        print("")
        assert response.status_code == 200
        if is_correct:
            assert judge == "1"
        else:
            assert judge != "1"
    else:
        print(f"Status {response.status_code}: NG...")
        print("")
        assert False, "API request failed"

# 問題IDのリストを取得
yaml_dir = Path(__file__).resolve().parent.parent / "problems" / "yaml_data"
if not yaml_dir.exists():
    print(f"Error: Directory not found -> {yaml_dir}")
    exit(1)
# ファイル名から拡張子を除いたものを問題IDとする
problem_ids = sorted([f.stem for f in yaml_dir.glob("*.yaml")])

# 正解チェック
for i, problem_id in enumerate(problem_ids):
    print(f"test num: {i} / {len(problem_ids)}")
    try:
        # APIを叩いて問題データを取得
        res = requests.get(f"{api_problems_url}/{problem_id}")
        if res.status_code != 200:
            print(f"Failed to fetch problem data for {problem_id}")
            continue
        problem_data = res.json()
        answer_shellgei = problem_data.get("answer", "")
        if not answer_shellgei:
            print(f"Skip {problem_id}: No answer found in API.")
            continue
        test_func(answer_shellgei, problem_id, True)
    except requests.exceptions.RequestException as e:
        print(f"Failed to connect to API for {problem_id}: {e}")

# 不正解チェック
test_func("echo tes", "STANDARD-00000001", False)
test_func("echo input.txt", "STANDARD-00000002", False)
test_func("seq 11", "STANDARD-00000003", False)
test_func(
    "echo \"scale=101; 4*a(1)\" | bc -l | tr -d '\\n' | tr -d '\\\\' | cut -c 1-103",
    "STANDARD-00000007",
    False,
)
test_func(
    "cat input.txt | awk '{for(i=0;i<10;i++){for(j=0;j<10;j++){if(i+j==$1&&i*2+j*4==$2){print i, j}}}}' | tr -d '\\n'",
    "STANDARD-00000008",
    False,
)
test_func(
    "cat input.txt | xargs | sed -E 's;([0-9]*/[0-9]*/[0-9]*);\\n\\1;g' | sort -r -k 1,1 | awk '{for(i=1;i<=NF;i++){print $i};printf(\"\\n\")}' | tr -d '\\n'",
    "STANDARD-00000009",
    False,
)
test_func("cat input.txt | tr -d '\\n'", "STANDARD-00000016", False)
test_func(
    "cat input.txt | awk 'NR==1{a=$1+$2+$3+$4+$5}NR==3{x=a-$1-$2-$4-$5;print $1,$2,x,$4,$5}NR!=3{print $0}' | sed '3 s/\\( [0-9] \\)/ \\1/g'",
    "STANDARD-00000042",
    False,
)
test_func("convert -size 200x200 xc:#FFFF00 media/output.jpg", "IMAGE-00000001", False)

# 成功メッセージ
print(f"Successfully!! ({server_url})")