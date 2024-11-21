root_path="/usr/share/nginx/"
root_path_html="/usr/share/nginx/html/"

is_local=$1

if [[ $is_local == "true" ]]; then
  root_path="/var/www/"
  root_path_html="/var/www/html/"
fi

# copy data
sudo cp -r ../data/problem_jp "$root_path_html"
sudo cp -r ../data/problem_en "$root_path_html"
sudo cp -r ../data/problem_images "$root_path_html"
sudo cp -r ../data/input "$root_path_html"
sudo cp -r ../data/output "$root_path_html"
sudo cp -r ../data/scripts "$root_path_html"

# copy client
sudo cp ../client/html/index.html "$root_path_html"
sudo cp ../client/html/index.en.html "$root_path_html"
sudo cp ../client/js/index.js "$root_path_html"
sudo cp ../client/css/style.css "$root_path_html"
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
find_target_str=$(find "$root_path")
target_str="shellgei_time.txt"
if [[ $find_target_str != *"$target_str"* ]]; then
  sudo touch "$root_path""$target_str"
  echo "2000-01-01 00:00:00" | sudo tee "$root_path""$target_str" >/dev/null 
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
if [[ $is_local == "true" ]]; then
  find "$root_path_html" | grep -e "index.js" -e "index*.html" | xargs -I@ sudo sed -i "s/https:\/\/shellgei-online-judge.com/http:\/\/localhost/g" @
fi