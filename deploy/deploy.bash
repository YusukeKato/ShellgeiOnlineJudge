# root_path="/usr/share/nginx/html/"
root_path="/var/www/html/"
soj_path="${root_path}soj/"
public_path="../backend/public/"

sudo rm -rf "$soj_path"
sudo mkdir -p "$soj_path"
sudo rm -rf "$public_path"
sudo mkdir -p "$public_path"
sudo cp -r ../frontend/build/* "$soj_path"
sudo cp -r ../problems/* "$soj_path"
sudo cp -r ../problems/* "$public_path"

sudo touch "${public_path}z.bash" && sudo chmod 777 "${public_path}z.bash" && echo "echo \"Hello, World!\"" > "${public_path}z.bash"
sudo touch "${public_path}unixtime.txt" && sudo chmod 666 "${public_path}unixtime.txt" && echo 0.0 > "${public_path}unixtime.txt"
sudo touch "${public_path}shellgei_id.txt" && sudo chmod 666 "${public_path}shellgei_id.txt" && echo 0 > "${public_path}shellgei_id.txt"

echo "deploy: success!!"
