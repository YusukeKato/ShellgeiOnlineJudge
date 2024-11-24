echo $(find ../problem_jp/ | grep GENERAL | wc -l) > cnt_general_num.txt
echo $(find ../problem_jp/ | grep EXERCISE | wc -l) > cnt_execise_num.txt
echo $(find ../problem_jp/ | grep IMAGE | wc -l) > cnt_image_num.txt
echo "update cnt_(general|execise|image)_num.txt"