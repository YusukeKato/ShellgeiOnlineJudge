#!/usr/bin/env bash
# 固定した公式debを検証し、job専用directoryへ展開する。systemへinstallしない。
set -euo pipefail
test "$(uname -m)" = x86_64
soj_plugin_dir="$(mktemp -d "${RUNNER_TEMP:?}/soj-ssm.XXXXXX")"
curl --fail --show-error --silent --location --max-time 120 \
  https://s3.amazonaws.com/session-manager-downloads/plugin/1.2.835.0/ubuntu_64bit/session-manager-plugin.deb \
  --output "$soj_plugin_dir/plugin.deb"
printf '7c6dcad12518571cc7959a713e6a8ae1bdf6ed66fd9bee37dc189e39ca58ae03  %s\n' \
  "$soj_plugin_dir/plugin.deb" | sha256sum --check --strict
dpkg-deb --extract "$soj_plugin_dir/plugin.deb" "$soj_plugin_dir/root"
soj_plugin_bin="$soj_plugin_dir/root/usr/local/sessionmanagerplugin/bin"
"$soj_plugin_bin/session-manager-plugin" --version
printf '%s\n' "$soj_plugin_bin" >> "${GITHUB_PATH:?}"
aws --version
