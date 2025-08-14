root_path="/usr/share/nginx/"
root_path_html="/usr/share/nginx/html/"

is_var=$1
is_local=$2

if [[ $is_var == "var" ]]; then
  echo "setup: /var/www/html"
  root_path="/var/www/"
  root_path_html="/var/www/html/"
else
  echo "setup: /usr/share/nginx/html/"
fi

# update files
# cd ../client/scripts
# python3 generate_index_html.py
# cd ../../data/scripts
# bash count_problem_num.bash
# cd ../../scripts

# delete files
find_target_str=$(find "$root_path")
target_str="connection.php"
if [[ $find_target_str == *"$target_str"* ]]; then
  # delete data
  sudo rm -rf "$root_path_html"problem_jp
  sudo rm -rf "$root_path_html"problem_en
  sudo rm -rf "$root_path_html"problem_images
  sudo rm -rf "$root_path_html"input
  sudo rm -rf "$root_path_html"output
  sudo rm -rf "$root_path_html"scripts
  sudo rm -rf "$root_path_html"soj-react-pkg
  
  # delete server
  sudo rm "$root_path_html"connection.php
  sudo rm "$root_path"run_shellgei.py
  sudo rm "$root_path"judge.py
  sudo rm "$root_path"z.bash
fi

# copy data
sudo cp -r ../data/problem_jp "$root_path_html"
sudo cp -r ../data/problem_en "$root_path_html"
sudo cp -r ../data/problem_images "$root_path_html"
sudo cp -r ../data/input "$root_path_html"
sudo cp -r ../data/output "$root_path_html"
sudo cp -r ../data/scripts "$root_path_html"

# copy client
# sudo cp ../client/html/index.html "$root_path_html"
# sudo cp ../client/html/index.en.html "$root_path_html"
# sudo cp ../client/js/index.js "$root_path_html"
# sudo cp ../client/css/style.css "$root_path_html"

# sudo cp ../client/svelte-soj-client/public/index.html "$root_path_html"
# sudo cp -r ../client/svelte-soj-client/public/build "$root_path_html"
# sudo cp ../client/svelte-soj-client/public/global.css "$root_path_html"
# sudo cp -r ../client/svelte-soj-client/scripts "$root_path_html"
# sudo cp -r ../client/svelte-soj-client/src "$root_path_html"
sudo cp -r ../client/soj-react-pkg/build/* "$root_path_html"

sudo cp ../client/images/BlackTreeIcon.jpg "$root_path_html"
sudo cp ../client/images/favicon.jpg "$root_path_html"
sudo cp ../client/images/white.jpg "$root_path_html"
sudo cp ../client/images/black.jpg "$root_path_html"

# copy server
sudo cp ../server/connection.php "$root_path_html"
sudo cp ../server/run_shellgei.py "$root_path"
sudo cp ../server/judge.py "$root_path"
sudo cp ../server/z.bash "$root_path"

# create files
target_str="shellgei_time.txt"
if [[ $find_target_str != *"$target_str"* ]]; then
  sudo touch "$root_path""$target_str"
  echo "2000-01-01 00:00:00" | sudo tee "$root_path""$target_str" >/dev/null 
  sudo chmod 766 "$root_path""$target_str"
  echo "create ""$root_path""$target_str"
fi
target_str="shellgei_time_ms.txt"
if [[ $find_target_str != *"$target_str"* ]]; then
  sudo touch "$root_path""$target_str"
  echo "0.0" | sudo tee "$root_path""$target_str" >/dev/null 
  sudo chmod 766 "$root_path""$target_str"
  echo "create ""$root_path""$target_str"
fi
target_str="shellgei_id.txt"
if [[ $find_target_str != *"$target_str"* ]]; then
  sudo touch "$root_path""$target_str"
  echo "0" | sudo tee "$root_path""$target_str" >/dev/null
  sudo chmod 766 "$root_path""$target_str"
  echo "create ""$root_path""$target_str"
fi
target_str="shellgei_log.txt"
if [[ $find_target_str != *"$target_str"* ]]; then
  sudo touch "$root_path""$target_str"
  sudo chmod 766 "$root_path""$target_str"
  echo "create ""$root_path""$target_str"
fi
target_str="debug.txt"
if [[ $find_target_str != *"$target_str"* ]]; then
  sudo touch "$root_path""$target_str"
  sudo chmod 766 "$root_path""$target_str"
  echo "create ""$root_path""$target_str"
fi

# chmod
sudo chmod 777 "$root_path"z.bash

# local
# if [[ $is_local == "local" ]]; then
#   echo "setup: local"
#   find "$root_path_html" | grep -e "index.js" -e "index.html" -e "index.en.html" | xargs -I@ sudo sed -i "s/https:\/\/shellgei-online-judge.com/http:\/\/localhost/g" @
# else
#   echo "setup: server"
# fi

echo "deploy: success!!"