root_path="/usr/share/nginx/html/"
# root_path="/var/www/html/"
soj_path="${root_path}soj/"
backend_path="../backend/"
public_path="${backend_path}public/"

sudo rm -rf "$soj_path"
sudo mkdir -p "$soj_path"
sudo cp -r ../frontend/build/* "$soj_path"
sudo cp -r ../problems/* "$soj_path"
sudo cp -r ../problems/* "$public_path"

sudo touch "${backend_path}z.bash" && sudo chmod 777 "${backend_path}z.bash" && echo "echo \"Hello, World!\"" > "${public_path}z.bash"
sudo touch "${backend_path}unixtime.txt" && sudo chmod 666 "${backend_path}unixtime.txt" && echo 0.0 > "${backend_path}unixtime.txt"
sudo touch "${backend_path}shellgei_id.txt" && sudo chmod 666 "${backend_path}shellgei_id.txt" && echo 0 > "${backend_path}shellgei_id.txt"

echo "deploy: success!!"
