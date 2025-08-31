import requests
import time
import sys
import os

args = sys.argv
main_url = 'https://shellgei-online-judge.com:8000/api/shellgei';
if len(args) > 1 and args[1] == "local":
  main_url = 'http://localhost:8000/api/shellgei';
  print("start test: local")
else:
  print("start test: server")

def test_func(shellgei, problem, is_correct):
    time.sleep(1.0)
    data = {  
      "shellgei": shellgei,
      "problem_id": problem,
    }
    response = requests.post(
      url=main_url,
      json=data,
    )
    print(problem+"\ninput: "+shellgei+"\noutput: "+response.json()["output"])
    if response.status_code == 200:
      print("Status 200: OK")
    else:
      print("Status " + str(response.status_code) + ": NG...")
    judge = response.json()["judge"].replace("\n","")
    if judge == "1":
      print("Correct!!")
    else:
      print("Incorrect...("+judge+")")
    print("")
    assert response.status_code == 200
    if is_correct:
      assert judge == "1"
    else:
      assert judge != "1"

# correct check
problem_filenames = sorted(os.listdir('../problems/statement/'))
i = 0
for file_name in problem_filenames:
  print('test num: ' + str(i) + ' / ' + str(len(problem_filenames)))
  answer_file_name = open('../problems/answer/'+ file_name, 'r', encoding='UTF-8')
  answer_shellgei = answer_file_name.read()
  test_func(answer_shellgei, file_name.replace(".txt", ""), True)
  i += 1

# incorrect check
test_func("echo tes", "GENERAL-00000001", False)
test_func("echo input.txt", "GENERAL-00000002", False)
test_func("seq 11", "GENERAL-00000003", False)
test_func("echo \"scale=101; 4*a(1)\" | bc -l | tr -d '\\n' | tr -d '\\\\' | cut -c 1-103", "GENERAL-00000007", False)
test_func("cat input.txt | awk '{for(i=0;i<10;i++){for(j=0;j<10;j++){if(i+j==$1&&i*2+j*4==$2){print i, j}}}}' | tr -d '\\n'", "GENERAL-00000008", False)
test_func("cat input.txt | xargs | sed -E 's;([0-9]*/[0-9]*/[0-9]*);\\n\\1;g' | sort -r -k 1,1 | awk '{for(i=1;i<=NF;i++){print $i};printf(\"\\n\")}' | tr -d '\\n'", "GENERAL-00000009", False)
test_func("cat input.txt | tr -d '\\n'", "GENERAL-00000016", False)
test_func("cat input.txt | awk \'NR==1{a=$1+$2+$3+$4+$5}NR==3{x=a-$1-$2-$4-$5;print $1,$2,x,$4,$5}NR!=3{print $0}\' | sed \'3 s/\\( [0-9] \\)/ \\1/g\'", "GENERAL-00000042", False)
test_func("convert -size 200x200 xc:#FFFF00 media/output.jpg", "IMAGE-00000001", False)

if len(args) > 1 and args[1] == "local":
  print("Successfully!! (local)")
else:
  print("Successfully!! (server)")