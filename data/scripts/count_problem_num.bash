echo $(find ../problem_jp/ | grep GENERAL | wc -l) > cnt_general_num.txt
echo $(find ../problem_jp/ | grep EXERCISE | wc -l) > cnt_execise_num.txt
echo $(find ../problem_jp/ | grep IMAGE | wc -l) > cnt_image_num.txt
echo $(find ../answer/ | grep EXERCISE-awk | wc -l) > cnt_exercise_awk_num.txt
echo $(find ../answer/ | grep EXERCISE-cat | wc -l) > cnt_exercise_cat_num.txt
echo $(find ../answer/ | grep EXERCISE-echo | wc -l) > cnt_exercise_echo_num.txt
echo $(find ../answer/ | grep EXERCISE-find | wc -l) > cnt_exercise_find_num.txt
echo $(find ../answer/ | grep EXERCISE-grep | wc -l) > cnt_exercise_grep_num.txt
echo $(find ../answer/ | grep EXERCISE-sed | wc -l) > cnt_exercise_sed_num.txt
echo $(find ../answer/ | grep EXERCISE-sort | wc -l) > cnt_exercise_sort_num.txt
echo $(find ../answer/ | grep EXERCISE-uniq | wc -l) > cnt_exercise_uniq_num.txt
echo $(find ../answer/ | grep EXERCISE-wc | wc -l) > cnt_exercise_wc_num.txt
echo "update cnt_(general|execise|image)_num.txt"