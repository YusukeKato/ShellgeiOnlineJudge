import React from "react";
import "../css/news.css";
import "../css/summary.css";
import "../css/common.css";

interface SojUrlsInterface {
  blog_url: string;
}

const SojNews: React.FC<SojUrlsInterface> = ({ blog_url }) => {
  return (
    <div className="soj-main">
      <h3>お知らせ / NEWS</h3>
      <ul>
        <li>2025/08/15: バージョン2.0.0リリース / Version 2.0.0 Released</li>
        <li>2025/05/03: シェル芸オンラインジャッジ二周年 / 2nd Anniversary</li>
        <li>2024/12/27: 安定版バージョン1.1.0リリース / Stable Version 1.1.0 Released</li>
        <li>2024/11/28: 回答例を追加 / Added Sample Answers</li>
        <li>2024/09/06: 画像問題を追加 / Added Image Problems</li>
      </ul>
      <div className="slide">
        <img src={`${blog_url}/images/news/news_20250503.jpg`} alt="slide-img-01" />
        <img src={`${blog_url}/images/news/news_20240503.jpg`} alt="slide-img-02" />
        <img src={`${blog_url}/images/news/news_20230503.jpg`} alt="slide-img-03" />
      </div>
      <details>
        <summary>過去のお知らせ / PAST NEWS</summary>
        <ul>
          <li>2024/05/03: シェル芸オンラインジャッジ一周年 / 1st Anniversary</li>
          <li>2024/04/24: 練習問題を追加 / Added Practice Problems</li>
          <li>2023/05/03: シェル芸オンラインジャッジ開始 / Shellgei Online Judge Launched</li>
        </ul>
      </details>
    </div>
  );
};

export default SojNews;
