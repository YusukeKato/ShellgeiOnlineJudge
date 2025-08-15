# Deploy

## nginx root path
- `usr`: `/usr/share/nginx/html/soj/main/`
- `var`: `/var/www/html/soj/main/`

## Edit server url

edit `frontend/src/tsx/App.tsx`

```sh
# server
const soj_url: string = "https://shellgei-online-judge.com";
# local
const soj_url: string = "http://localhost";
```

## Deploy
execute the following command:

```sh
# usr
./deploy.bash usr
# var
./deploy.bash var
```

## Test
execute the following command:

```sh
# server
python3 test.py server
# local
python3 test.py local
```