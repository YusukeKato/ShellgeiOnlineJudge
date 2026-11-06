#!/bin/sh
# 初回APT取得をHTTPS・検証済みCA・再試行なしで保護し、署名検証を維持して修正版へ更新する。
# 引数はdistributionと既に信頼したCA bundle。終了非0なら後続installを実行しない。
set -eu
test "$#" -eq 2
distribution="$1"
ca_bundle="$2"
test -s "$ca_bundle"
case "$distribution" in
  debian) source_file=/etc/apt/sources.list.d/debian.sources; version=3.0.4; library=libapt-pkg7.0 ;;
  ubuntu) source_file=/etc/apt/sources.list.d/ubuntu.sources; version=2.8.4ubuntu0.1; library=libapt-pkg6.0t64 ;;
  *) echo "unsupported APT distribution" >&2; exit 1 ;;
esac
test -f "$source_file" && test ! -L "$source_file"
# 固定base以外の有効な取得元を黙って残さず、設定の増加時は先に見直す。
for file in /etc/apt/sources.list /etc/apt/sources.list.d/*.list /etc/apt/sources.list.d/*.sources; do
  test -f "$file" || continue
  test "$file" != "$source_file" || continue
  if grep -Eq '^[[:space:]]*(deb(-src)?[[:space:]]|URIs:)' "$file"; then
    echo "unexpected active APT source: $file" >&2
    exit 1
  fi
done
sed -i 's|http://|https://|g' "$source_file"
awk '/^URIs:/ { count++; for (i=2;i<=NF;i++) if ($i !~ /^https:\/\//) exit 1 } END { if (!count) exit 1 }' "$source_file"
# 古いAPTが残るbootstrap中はredirectとretryを止める。TLSとpackage署名の検証は無効化しない。
cat > /etc/apt/apt.conf.d/99soj-apt-bootstrap <<EOF
Acquire::Retries "0";
Acquire::http::AllowRedirect "false";
Acquire::https::AllowRedirect "false";
Acquire::https::Verify-Peer "true";
Acquire::https::Verify-Host "true";
Acquire::https::CaInfo "$ca_bundle";
EOF
apt-get update
DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends --only-upgrade "apt=$version" "$library=$version"
for package in apt "$library"; do
  actual="$(dpkg-query -W -f='${Version}' "$package")"
  dpkg --compare-versions "$actual" ge "$version"
done
# callerは同じRUN内の残りの取得を終えてからbootstrap設定・一時CA・listを削除する。
