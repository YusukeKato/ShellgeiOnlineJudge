import React from "react";
import "./summary.css";
import "./headline.css";
import "./common.css";

interface SojUrlsInterface {
  x_url: string;
  github_url: string;
  github_author_url: string;
  blog_url: string;
  mixi2_url: string;
}

const SojContact: React.FC<SojUrlsInterface> = ({
  x_url,
  github_url,
  github_author_url,
  blog_url,
  mixi2_url,
}) => {
  return (
    <div className="soj-main">
      <details>
        <summary>お問い合わせ / CONTACT</summary>
        <h4>SNS</h4>
        <ul>
          <li>
            X/Twitter：<a href={x_url}>@yusukekato_main</a>
          </li>
          <li>タグ：#シェル芸オンラインジャッジ</li>
          <li>Tag：#ShellgeiOnlineJudge</li>
          <li>
            mixi2：<a href={mixi2_url}>シェル芸オンラインジャッジのコミュニティ / Community</a>
          </li>
        </ul>
        <h4>GITHUB</h4>
        <ul>
          <li>
            <a href={github_url + "/discussions"}>GitHub - Discussions</a>
          </li>
          <li>
            <a href={github_url + "/issues"}>GitHub - Issues</a>
          </li>
        </ul>
        <h4>AUTHOR</h4>
        <ul>
          <li>
            GitHub : <a href={github_author_url}>YusukeKato</a>
          </li>
          <li>
            Blog : <a href={blog_url}>yusukekato.jp</a>
          </li>
        </ul>
      </details>
    </div>
  );
};

export default SojContact;
