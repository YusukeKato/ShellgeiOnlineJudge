import requests
# import json
# import pytest
import time
import sys

args = sys.argv
main_url = 'https://shellgei-online-judge.com/connection.php';
if len(args) > 1 and args[1] == "local":
  main_url = 'http://localhost/connection.php';
  print("start test: local")
else:
  print("start test: server")

def test_func(shellgei, problemNum, is_correct):
    time.sleep(0.5)
    data = {  
      "shellgei": shellgei,
      "problemNum": problemNum
    }
    response = requests.post(
      url=main_url,
      data=data,
    )
    print(problemNum+"\ninput: "+shellgei+"\noutput: "+response.json()["shellgei"])
    if response.status_code == 200:
      print("Status 200: OK")
    else:
      print("Status " + str(response.status_code) + ": NG...")
    judge = response.json()["shellgei_judge"].replace("\n","")
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

# GENERAL
f_cnt_general_num = open('../data/scripts/cnt_general_num.txt', 'r', encoding='UTF-8')
cnt_general_num = f_cnt_general_num.read().replace("\n","")
for i in range(int(cnt_general_num)):
  file_name = "GENERAL-" + str(i+1).zfill(8)
  f_answer = open('../data/answer/'+ file_name +'.txt', 'r', encoding='UTF-8')
  answer_shellgei = f_answer.read()
  test_func(answer_shellgei, file_name, True)

# EXERCISE
cmd_list = ["awk", "cat", "echo", "find", "grep", "sed", "sort", "uniq", "wc"]
for j in range(len(cmd_list)):
  f_cnt_exercise_num = open('../data/scripts/cnt_exercise_' + cmd_list[j] + '_num.txt', 'r', encoding='UTF-8')
  cnt_exercise_num = f_cnt_exercise_num.read().replace("\n","")
  for i in range(int(cnt_exercise_num)):
    file_name = "EXERCISE-" + cmd_list[j] + "-" + str(i+1).zfill(2)
    f_answer = open('../data/answer/'+ file_name +'.txt', 'r', encoding='UTF-8')
    answer_shellgei = f_answer.read()
    test_func(answer_shellgei, file_name, True)

# IMAGE
f_cnt_image_num = open('../data/scripts/cnt_image_num.txt', 'r', encoding='UTF-8')
cnt_image_num = f_cnt_image_num.read().replace("\n","")
for i in range(int(cnt_image_num)):
  file_name = "IMAGE-" + str(i+1).zfill(8)
  f_answer = open('../data/answer/'+ file_name +'.txt', 'r', encoding='UTF-8')
  answer_shellgei = f_answer.read()
  test_func(answer_shellgei, file_name, True)

# incorrect
# G1
test_func("echo tes", "GENERAL-00000001", False)
# G2
test_func("echo input.txt", "GENERAL-00000002", False)
# G3
test_func("seq 11", "GENERAL-00000003", False)
# G7
test_func("echo \"scale=101; 4*a(1)\" | bc -l | tr -d '\\n' | tr -d '\\\\' | cut -c 1-103", "GENERAL-00000007", False)
# G8
test_func("cat input.txt | awk '{for(i=0;i<10;i++){for(j=0;j<10;j++){if(i+j==$1&&i*2+j*4==$2){print i, j}}}}' | tr -d '\\n'", "GENERAL-00000008", False)
# G9
test_func("cat input.txt | xargs | sed -E 's;([0-9]*/[0-9]*/[0-9]*);\\n\\1;g' | sort -r -k 1,1 | awk '{for(i=1;i<=NF;i++){print $i};printf(\"\\n\")}' | tr -d '\\n'", "GENERAL-00000009", False)
# G16
test_func("cat input.txt | tr -d '\\n'", "GENERAL-00000016", False)
# G42
test_func("cat input.txt | awk \'NR==1{a=$1+$2+$3+$4+$5}NR==3{x=a-$1-$2-$4-$5;print $1,$2,x,$4,$5}NR!=3{print $0}\' | sed \'3 s/\\( [0-9] \\)/ \\1/g\'", "GENERAL-00000042", False)
# I1
test_func("convert -size 200x200 xc:#FFFF00 media/output.jpg", "IMAGE-00000001", False)

if len(args) > 1 and args[1] == "local":
  print("Successfully!! (local)")
else:
  print("Successfully!! (server)")