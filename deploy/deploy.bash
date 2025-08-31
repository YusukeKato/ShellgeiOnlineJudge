sudo rm -rf "./public"
sudo mkdir -p "./public"

sudo cp -r ../frontend/build/* "./public/"
sudo cp -r ../problems/* "./public/"

echo "deploy: success!!"