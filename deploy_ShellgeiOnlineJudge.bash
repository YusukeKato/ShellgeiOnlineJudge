root_path="/usr/share/nginx/"
root_path_html="/usr/share/nginx/html/"

# delete data
sudo rm -rf "$root_path_html"problem_jp
sudo rm -rf "$root_path_html"problem_en
sudo rm -rf "$root_path_html"problem_images
sudo rm -rf "$root_path_html"input
sudo rm -rf "$root_path_html"output

# delete web app
sudo rm "$root_path_html"index.html
sudo rm "$root_path_html"index.en.html
sudo rm "$root_path_html"index.js
sudo rm "$root_path_html"style.css
sudo rm "$root_path_html"BlackTreeIcon.jpg
sudo rm "$root_path_html"favicon.jpg
sudo rm "$root_path_html"white.jpg
sudo rm "$root_path_html"black.jpg

# delete server
sudo rm "$root_path_html"connection.php
sudo rm "$root_path"run_shellgei.py
sudo rm "$root_path"z.bash

# copy data
sudo rm -rf ShellgeiOnlineJudgeData
git clone https://github.com/YusukeKato/ShellgeiOnlineJudgeData.git
sudo cp -r ShellgeiOnlineJudgeData/problem_jp "$root_path_html"
sudo cp -r ShellgeiOnlineJudgeData/problem_en "$root_path_html"
sudo cp -r ShellgeiOnlineJudgeData/problem_images "$root_path_html"
sudo cp -r ShellgeiOnlineJudgeData/input "$root_path_html"
sudo cp -r ShellgeiOnlineJudgeData/output "$root_path_html"

# copy web app
sudo rm -rf ShellgeiOnlineJudgeWeb
git clone https://github.com/YusukeKato/ShellgeiOnlineJudgeWeb.git
sudo cp ShellgeiOnlineJudgeWeb/html/index.html "$root_path_html"
sudo cp ShellgeiOnlineJudgeWeb/html/index.en.html "$root_path_html"
sudo cp ShellgeiOnlineJudgeWeb/js/index.js "$root_path_html"
sudo cp ShellgeiOnlineJudgeWeb/css/style.css "$root_path_html"
sudo cp ShellgeiOnlineJudgeWeb/images/BlackTreeIcon.jpg "$root_path_html"
sudo cp ShellgeiOnlineJudgeWeb/images/favicon.jpg "$root_path_html"
sudo cp ShellgeiOnlineJudgeWeb/images/white.jpg "$root_path_html"
sudo cp ShellgeiOnlineJudgeWeb/images/black.jpg "$root_path_html"

# copy server
sudo rm -rf ShellgeiOnlineJudgeServer
git clone https://github.com/YusukeKato/ShellgeiOnlineJudgeServer.git
sudo cp ShellgeiOnlineJudgeServer/connection.php "$root_path_html"
sudo cp ShellgeiOnlineJudgeServer/run_shellgei.py "$root_path"
sudo cp ShellgeiOnlineJudgeServer/z.bash "$root_path"
sudo chmod 777 "$root_path"z.bash
