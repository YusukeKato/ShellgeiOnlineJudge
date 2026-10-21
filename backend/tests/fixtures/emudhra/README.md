# eMudhra CA回帰fixture

公開証明書だけを収録し、秘密鍵や攻撃用の証明書生成処理は含みません。
検査実装は[ci/check_ca_trust.py](../../../../ci/check_ca_trust.py)です。

- 12本のTLS chain: https://emudhra.we-have-a-problem.com/chains.zip
  - 公開側の採取日: 2026-10-20
  - archive SHA-256: `8a2edc81b6c51e3ad27d45ca1e441ec84c961e2dee0fc547f2a02c0f74315f95`
- `compromised-root.pem`: 同サイトのroots.jsonにあるemSign ECC Root CA - G3。
  拒否検査がrootの再追加を検知することを確かめるnegative control専用です。
- `shellgei-online-judge.com.pem`: 2026-10-22に公開SOJからTLS検証付きで取得した正常chain。
  leaf SHA-256: `b80356d33d1e32d586bcaa4c6129243ae9f92abeba2f3c042328684f01c1768f`
- `control-root.pem`: 正常chainのanchorであるISRG Root X1公開証明書。

検証時刻は採取日のUTC 00:00に固定します。将来の期限切れをCA不信頼と誤認せず、
12 chainがissuer不信頼で拒否され、正常chainが許可されることを同じ条件で確認します。
fixture更新時は出典・hash・時刻を揃えて再検証してください。
