is_var=$1
root_path_html="/usr/share/nginx/html/"
root_path_soj="/usr/share/nginx/html/soj/"
root_path_main="/usr/share/nginx/html/soj/main/"
if [[ $is_var == "var" ]]; then
  root_path_html="/var/www/html/"
  root_path_soj="/var/www/html/soj/"
  root_path_main="/var/www/html/soj/main/"
  echo "setup: /var/www/html/soj/main/"
else
  echo "setup: /usr/share/nginx/html/soj/main/"
fi

sudo rm -rf "$root_path_soj"
sudo mkdir -p "$root_path_main"

sudo cp -r ../frontend/build/* "$root_path_main"
sudo cp -r ../problems/* "$root_path_main"
sudo cp ../backend/connection.php "$root_path_main"
sudo cp ../backend/run_shellgei.py "$root_path_soj"
sudo cp ../backend/judge.py "$root_path_soj"
sudo cp ../backend/z.bash "$root_path_soj"

find_target_html=$(find "$root_path_html")
target_str="shellgei_time_ms.txt"
if [[ $find_target_html != *"$target_str"* ]]; then
  sudo touch "$root_path_html""$target_str"
  echo "0.0" | sudo tee "$root_path_html""$target_str" >/dev/null
  sudo chmod 766 "$root_path_html""$target_str"
fi
target_str="shellgei_id.txt"
if [[ $find_target_html != *"$target_str"* ]]; then
  sudo touch "$root_path_html""$target_str"
  echo "0" | sudo tee "$root_path_html""$target_str" >/dev/null
  sudo chmod 766 "$root_path_html""$target_str"
fi
target_str="shellgei_log.txt"
if [[ $find_target_html != *"$target_str"* ]]; then
  sudo touch "$root_path_html""$target_str"
  sudo chmod 766 "$root_path_html""$target_str"
fi
target_str="debug.txt"
if [[ $find_target_html != *"$target_str"* ]]; then
  sudo touch "$root_path_html""$target_str"
  sudo chmod 766 "$root_path_html""$target_str"
fi

sudo chmod 777 "$root_path_soj""z.bash"

echo "deploy: success!!"