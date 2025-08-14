import React from "react";
import "../css/summary.css";
import "../css/code.css";
import "../css/common.css";

const SojAbout: React.FC = () => {
  return (
    <div className="soj-main">
      <h3>詳細 / DETAILS</h3>
      <details>
        <summary>シェル芸オンラインジャッジについて / ABOUT SOJ</summary>
        <h4>シェル芸オンラインジャッジとは / WHAT'S SOJ</h4>
        <p>
          シェル芸で問題を解いて遊べるシェル芸非公式のウェブサイトです。実行結果の正誤判定が自動で行われます。
        </p>
        <p>
          SHELLGEI ONLINE JUDGE is Un-official website. This website automatically judges whether
          the execution results are correct.
        </p>
        <h4>シェル芸とは / WHAT'S SHELLGEI</h4>
        <p>
          シェル芸とはCLI環境におけるシェルのワンライナーで様々なタスクをこなすことを指します。詳しくは
          <a href="https://b.ueda.tech/?page=01434">シェル芸のトップページ</a>を参照してください。
        </p>
        <p>Shell-gei is a shell one-liner that performs various tasks in the CLI environment.</p>
        <h4>シェル芸の例 / EXAMPLES OF SHELLGEI</h4>
        <p>Example 1: Output random String</p>
        <div className="code-block">
          <pre>
            <code className="code-font">
              head -c 65536 /dev/urandom | tr -dc a-zA-Z0-9 | cut -c -16
            </code>
          </pre>
        </div>
        <p>Example 2: Delete all .jpg files</p>
        <div className="code-block">
          <pre>
            <code className="code-font">find /tmp | grep .jpg$ | xargs -I@ rm @</code>
          </pre>
        </div>
        <h4>GITHUB</h4>
        <ul>
          <li>
            <a href="https://github.com/YusukeKato/ShellgeiOnlineJudge">
              GitHub - ShellgeiOnlineJudge
            </a>
          </li>
          <li>
            <a href="https://github.com/YusukeKato/ShellgeiOnlineJudge/discussions">
              GitHub - SHELLGEI ONLINE JUDGE Discussions
            </a>
          </li>
        </ul>
        <h4>利用・参考情報 / REFERENCES</h4>
        <p>下記のコンテンツを利用や参考にさせていただきました。</p>
        <ul>
          <li>
            <a href="https://github.com/theoremoon/ShellgeiBot-Image">
              theoremoon/ShellgeiBot-Image
            </a>
          </li>
          <li>
            <a href="https://github.com/ryuichiueda/ShellGeiData">ryuichiueda/ShellGeiData</a>
          </li>
          <li>
            <a href="https://github.com/jiro4989/websh">jiro4989/websh</a>
          </li>
          <li>
            <a href="https://judge.u-aizu.ac.jp/onlinejudge/">AIZU ONLINE JUDGE</a>
          </li>
          <li>
            <a href="https://atcoder.jp/">AtCoder</a>
          </li>
          <li>
            <a href="https://twitter.com/minyoruminyon">シェル芸bot</a>
          </li>
        </ul>
        <h4>遊び方 / HOW TO PLAY</h4>
        <ol>
          <li>問題を選択 / Select Problem</li>
          <li>シェル芸を記入 / Enter Shell One-liner</li>
          <li>シェル芸を実行 / Execute Shell One-liner</li>
          <li>正誤判定の結果を確認 / Check Result</li>
        </ol>
      </details>
    </div>
  );
};

export default SojAbout;
