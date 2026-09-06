#!/usr/bin/env bash
# GitHub-hosted runnerだけで、setup-docker-actionのdaemonにuser D-Busを引き継ぐ。
set -euo pipefail

if [[ ${GITHUB_ACTIONS:-} != true || ${RUNNER_ENVIRONMENT:-} != github-hosted || $(id -u) != 1001 ]]; then
  echo 'This setup is only for the GitHub-hosted runner used by setup-docker-action.' >&2
  exit 1
fi

soj_runner_user="$(id -un)"
[[ $soj_runner_user =~ ^[a-z_][a-z0-9_-]*$ ]]
sudo apt-get update
sudo apt-get install --yes dbus-user-session
# Delegateは既存serviceへset-propertyできないため、runtime drop-inから読み込ませる。
sudo mkdir -p /run/systemd/system/user@1001.service.d
printf '[Service]\nDelegate=cpu cpuset io memory pids\n' \
  | sudo tee /run/systemd/system/user@1001.service.d/soj-delegate.conf > /dev/null
sudo systemctl daemon-reload
sudo systemctl start user@1001.service
sudo systemctl show user@1001.service --property=Delegate --property=DelegateControllers
export XDG_RUNTIME_DIR=/run/user/1001
export DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1001/bus
systemctl --user start dbus.service
test -S /run/user/1001/bus
busctl --user --no-pager status

# Actionは独自のXDG_RUNTIME_DIRを設定し、sudo -u経由で起動する。
# busの明示指定だけをrunnerのsudo環境に残す。権限の追加は行わない。
printf 'Defaults:%s env_keep += "DBUS_SESSION_BUS_ADDRESS"\n' "$soj_runner_user" \
  | sudo tee /etc/sudoers.d/soj-rootless-dbus > /dev/null
sudo chmod 0440 /etc/sudoers.d/soj-rootless-dbus
sudo visudo --check --file /etc/sudoers.d/soj-rootless-dbus
test "$(sudo -u '#1001' printenv DBUS_SESSION_BUS_ADDRESS)" = "$DBUS_SESSION_BUS_ADDRESS"
printf 'DBUS_SESSION_BUS_ADDRESS=%s\n' "$DBUS_SESSION_BUS_ADDRESS" >> "$GITHUB_ENV"
