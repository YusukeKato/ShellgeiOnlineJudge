import React from "react";
import "../css/summary.css";
import "../css/headline.css";
import "../css/common.css";

const SojOthers: React.FC = () => {
  return (
    <div className="soj-main">
      <details>
        <summary>その他 / OTHERS</summary>
        <h4>注意事項 / NOTES</h4>
        <p>
          このウェブサイトではGoogle AnalyticsとGoogle Search
          Consoleを利用しています。このウェブサイトの利用によって生じる損害等について一切責任を負いません。実行されたコマンド等の情報は記録されます。
        </p>
        <p>
          This website uses Google Analytics and Google Search Console. We are not responsible for
          any damages caused by the use of this website. Information about executed commands will be
          recorded.
        </p>
        <h4>有志の方々 / CONTRIBUTORS</h4>
        <p>回答例を提供いただき、誠にありがとうございます。</p>
        <p>Thank you very much for the example answer.</p>
        <ul>
          <li>
            <a href="https://gist.github.com/eggplants/71c0459f38028938a15d35b19bab47b5">
              eggplants/ans.csv
            </a>
          </li>
          <li>
            <a href="https://shellgei.wiki/?cat=5">シェル芸非公式WIKI</a>
          </li>
        </ul>
        <h4>回答例 / EXAMPLE ANSWERS</h4>
        <a href="https://github.com/YusukeKato/ShellgeiOnlineJudge/tree/main/problems/yaml_data">
          GitHub - problems/yaml_data/
        </a>
        <h4>おすすめ / RECOMMENDS</h4>
        <p>さらに難しい問題や面白い問題が解きたい方には以下がおすすめです。</p>
        <p>
          For those who want to solve more difficult and interesting problems, we recommend the
          following.
        </p>
        <ul>
          <li>
            <a href="https://b.ueda.tech/?page=00684">シェル芸勉強会問題一覧</a>
          </li>
          <li>
            <a href="https://atcoder.jp/">AtCoder: 競技プログラミング / Competitive Programming</a>
          </li>
        </ul>
      </details>
    </div>
  );
};

export default SojOthers;
