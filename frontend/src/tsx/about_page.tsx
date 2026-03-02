import React from "react";
import "../css/summary.css";
import "../css/headline.css";
import "../css/code.css";
import "../css/common.css";

interface AboutPageProps {
  update_date: string;
  current_version: string;
  x_url: string;
  github_repository_url: string;
  github_author_url: string;
  blog_url: string;
  mixi2_url: string;
}

const AboutPage: React.FC<AboutPageProps> = ({
  update_date,
  current_version,
  x_url,
  github_repository_url,
  github_author_url,
  blog_url,
  mixi2_url,
}) => {
  return (
    <>
      {/* 概要 / INFORMATION */}
      <div className="soj-main">
        <h2>最終更新日 / LAST UPDATED</h2>
        <ul>
          <li>update: {update_date}</li>
          <li>version: {current_version}</li>
        </ul>
      </div>

      {/* 詳細 / DETAILS */}
      <div className="soj-main">
        <h2>情報 / INFOMATION</h2>
        <h3>シェル芸オンラインジャッジとは / WHAT'S SHELLGEI ONLINE JUDGE</h3>
        <p>
          シェル芸で問題を解いて遊べるシェル芸非公式のウェブサイトです。実行結果の正誤判定が自動で行われます。
        </p>
        <p>
          SHELLGEI ONLINE JUDGE is Un-official website. This website automatically judges whether
          the execution results are correct.
        </p>
        <h3>シェル芸とは / WHAT'S SHELLGEI</h3>
        <p>
          シェル芸とはCLI環境におけるシェルのワンライナーで様々なタスクをこなすことを指します。詳しくは
          <a href="https://b.ueda.tech/?page=01434" target="_blank" rel="noopener noreferrer">
            シェル芸のトップページ
          </a>
          を参照してください。
        </p>
        <p>Shell-gei is a shell one-liner that performs various tasks in the CLI environment.</p>
        <h3>GITHUB</h3>
        <ul>
          <li>
            <a href={github_repository_url} target="_blank" rel="noopener noreferrer">
              GitHub - ShellgeiOnlineJudge
            </a>
          </li>
          <li>
            <a
              href={`${github_repository_url}/discussions`}
              target="_blank"
              rel="noopener noreferrer"
            >
              GitHub - SHELLGEI ONLINE JUDGE Discussions
            </a>
          </li>
          <li>
            <a
              href={`${github_repository_url}/blob/main/UPDATE_HISTORY.md`}
              target="_blank"
              rel="noopener noreferrer"
            >
              GitHub - Update History
            </a>
          </li>
        </ul>
        <h3>遊び方 / HOW TO PLAY</h3>
        <ol>
          <li>問題を選択 / Select Problem</li>
          <li>シェル芸を記入 / Enter Shell One-liner</li>
          <li>シェル芸を実行 / Execute Shell One-liner</li>
          <li>正誤判定の結果を確認 / Check Result</li>
        </ol>
      </div>

      {/* お問い合わせ / CONTACT */}
      <div className="soj-main">
        <h2>お問い合わせ / CONTACT</h2>
        <h3>SNS</h3>
        <ul>
          <li>
            X/Twitter：
            <a href={x_url} target="_blank" rel="noopener noreferrer">
              @yusukekato_main
            </a>
          </li>
          <li>タグ：#シェル芸オンラインジャッジ</li>
          <li>Tag：#ShellgeiOnlineJudge</li>
          <li>
            mixi2：
            <a href={mixi2_url} target="_blank" rel="noopener noreferrer">
              シェル芸オンラインジャッジのコミュニティ / Community
            </a>
          </li>
        </ul>
        <h3>GITHUB</h3>
        <ul>
          <li>
            <a
              href={`${github_repository_url}/discussions`}
              target="_blank"
              rel="noopener noreferrer"
            >
              GitHub - Discussions
            </a>
          </li>
          <li>
            <a href={`${github_repository_url}/issues`} target="_blank" rel="noopener noreferrer">
              GitHub - Issues
            </a>
          </li>
        </ul>
        <h3>AUTHOR</h3>
        <ul>
          <li>
            GitHub :{" "}
            <a href={github_author_url} target="_blank" rel="noopener noreferrer">
              YusukeKato
            </a>
          </li>
          <li>
            Blog :{" "}
            <a href={blog_url} target="_blank" rel="noopener noreferrer">
              yusukekato.jp
            </a>
          </li>
        </ul>
      </div>

      {/* その他 / OTHERS */}
      <div className="soj-main">
        <h2>その他 / OTHERS</h2>
        <h3>注意事項 / NOTES</h3>
        <p>
          このウェブサイトではGoogle AnalyticsとGoogle Search Consoleを利用しています。
          このウェブサイトの利用によって生じる損害等について一切責任を負いません。
          実行されたコマンド等の情報は記録されます。
        </p>
        <p>
          This website uses Google Analytics and Google Search Console. We are not responsible for
          any damages caused by the use of this website. Information about executed commands will be
          recorded.
        </p>
        <h3>有志の方々 / CONTRIBUTORS</h3>
        <p>回答例を提供いただき、誠にありがとうございます。</p>
        <p>Thank you very much for the example answer.</p>
        <ul>
          <li>
            <a
              href="https://gist.github.com/eggplants/71c0459f38028938a15d35b19bab47b5"
              target="_blank"
              rel="noopener noreferrer"
            >
              eggplants/ans.csv
            </a>
          </li>
        </ul>
        <h3>回答例 / EXAMPLE ANSWERS</h3>
        <a
          href={`${github_repository_url}/tree/main/problems/yaml_data`}
          target="_blank"
          rel="noopener noreferrer"
        >
          GitHub - problems/yaml_data/
        </a>
        <h3>おすすめ / RECOMMENDS</h3>
        <p>さらに難しい問題や面白い問題が解きたい方には以下がおすすめです。</p>
        <p>
          For those who want to solve more difficult and interesting problems, we recommend the
          following.
        </p>
        <ul>
          <li>
            <a href="https://b.ueda.tech/?page=00684" target="_blank" rel="noopener noreferrer">
              シェル芸勉強会問題一覧
            </a>
          </li>
          <li>
            <a href="https://atcoder.jp/" target="_blank" rel="noopener noreferrer">
              AtCoder: 競技プログラミング / Competitive Programming
            </a>
          </li>
        </ul>
      </div>
    </>
  );
};

export default AboutPage;
