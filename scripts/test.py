import requests
# import json
# import pytest
import time
import sys

args = sys.argv
main_url = 'https://shellgei-online-judge.com/connection.php';
if len(args) > 1 and args[1] == "local":
  main_url = 'http://localhost/connection.php';

def test_func(shellgei, problemNum, is_correct):
    time.sleep(3)
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

test_func("echo test", "GENERAL-00000001", True)
test_func("cat input.txt", "GENERAL-00000002", True)
test_func("seq 10", "GENERAL-00000003", True)
test_func("convert -size 200x200 xc:#FF0000 media/output.jpg", "IMAGE-00000001", True)
test_func("echo tes", "GENERAL-00000001", False)
test_func("echo input.txt", "GENERAL-00000002", False)
test_func("seq 11", "GENERAL-00000003", False)
test_func("convert -size 200x200 xc:#FFFF00 media/output.jpg", "IMAGE-00000001", False)
print("Successfully!!")
