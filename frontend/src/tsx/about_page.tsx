import React, { type ReactNode } from "react";
import { useLanguage } from "../language";
import { CONTACT_FORM_URL } from "../links";

interface AboutPageProps {
  update_date: string;
  current_version: string;
  x_url: string;
  github_repository_url: string;
  github_author_url: string;
  blog_url: string;
  mixi2_url: string;
}

// 外部ページを別タブで開くことを支援技術にも伝え、リンク元のwindowを共有しない。
function ExternalLink({
  href,
  children,
  className,
}: {
  href: string;
  children: ReactNode;
  className?: string;
}) {
  const { text } = useLanguage();
  return (
    <a href={href} target="_blank" rel="noopener noreferrer" className={className}>
      {children}
      <span aria-hidden="true"> ↗</span>
      <span className="visually-hidden">
        {text("（別タブで開きます）", " (opens in a new tab)")}
      </span>
    </a>
  );
}

// 遊び方から問い合わせ・関連情報へ読み進められる順に、選択中の言語だけを表示する。
const AboutPage: React.FC<AboutPageProps> = ({
  update_date,
  current_version,
  x_url,
  github_repository_url,
  github_author_url,
  blog_url,
  mixi2_url,
}) => {
  const { text } = useLanguage();

  return (
    <div className="about-page">
      <div className="page-heading">
        <p className="eyebrow">{text("ガイド", "Guide")}</p>
        <h1>{text("使い方・情報", "About this playground")}</h1>
        <p className="muted">
          {text(
            "シェルのコマンドを組み合わせて、ワンライナーで問題を解いてみましょう。",
            "Combine shell commands into a one-liner and solve a problem.",
          )}
        </p>
        <p className="version-label">version: {current_version}</p>
        {update_date && (
          <p className="muted">
            {text("最終更新日", "Last updated")}: {update_date}
          </p>
        )}
      </div>

      <div className="about-grid">
        <section className="panel about-section" aria-labelledby="about-overview">
          <h2 id="about-overview">
            {text("シェル芸オンラインジャッジとは", "What is Shellgei Online Judge?")}
          </h2>
          <p>
            {text(
              "シェル芸で問題を解いて遊べる非公式のウェブサイトです。実行したコマンドの出力を、問題の期待する結果と自動で比較します。",
              "An unofficial playground for solving problems with shell one-liners. Your command output is automatically checked against the expected result.",
            )}
          </p>
          <p>
            {text(
              "シェル芸とは、CLI環境でシェルのワンライナーを使い、さまざまなタスクをこなすことです。",
              "Shell-gei is the art of accomplishing tasks with shell one-liners in a command-line environment.",
            )}
          </p>
          <ExternalLink href="https://b.ueda.tech/?page=01434">
            {text("シェル芸について詳しく知る", "Learn more about shell-gei")}
          </ExternalLink>
        </section>

        <section className="panel about-section" aria-labelledby="about-how-to">
          <h2 id="about-how-to">{text("遊び方", "How to play")}</h2>
          <ol>
            <li>
              {text(
                "カテゴリと問題を選び、問題文と入出力を確認します。",
                "Choose a category and problem, then read the statement and expected input and output.",
              )}
            </li>
            <li>
              {text(
                "コマンド欄にシェルのワンライナーを入力します。",
                "Write a shell one-liner in the command editor.",
              )}
            </li>
            <li>
              {text(
                "「実行する」を押して、判定と出力を確認します。",
                "Select Run to see the verdict and command output.",
              )}
            </li>
            <li>
              {text(
                "コマンドを工夫して、何度でも挑戦できます。",
                "Refine your command and try again.",
              )}
            </li>
          </ol>
          <p className="muted">
            {text(
              "実行したコマンド等の情報は記録されます。秘密情報は入力しないでください。",
              "Executed commands and related information are recorded. Do not enter secrets.",
            )}
          </p>
        </section>

        <section className="panel about-section" aria-labelledby="about-contact">
          <h2 id="about-contact">{text("お問い合わせ", "Contact")}</h2>
          <p>
            {text(
              "不具合の報告、ご質問、ご意見はこちらからお送りください。",
              "Send a bug report, ask a question, or share feedback.",
            )}
          </p>
          <ExternalLink href={CONTACT_FORM_URL} className="primary-link">
            {text("お問い合わせフォーム", "Contact form")}
          </ExternalLink>
          <p className="muted">
            {text("Googleフォームを別タブで開きます。", "Opens Google Forms in a new tab.")}
          </p>
          <ul className="link-list">
            <li>
              <ExternalLink href={`${github_repository_url}/discussions`}>
                GitHub Discussions
              </ExternalLink>
            </li>
            <li>
              <ExternalLink href={`${github_repository_url}/issues`}>GitHub Issues</ExternalLink>
            </li>
            {x_url && (
              <li>
                <ExternalLink href={x_url}>X / @yusukekato_main</ExternalLink>
              </li>
            )}
            {mixi2_url && (
              <li>
                <ExternalLink href={mixi2_url}>
                  {text("mixi2 コミュニティ", "mixi2 community")}
                </ExternalLink>
              </li>
            )}
          </ul>
          <p className="social-tag">
            {text(
              "SNS等で使用するタグ：#シェル芸オンラインジャッジ",
              "Hashtag for social media: #ShellgeiOnlineJudge",
            )}
          </p>
        </section>

        <section className="panel about-section" aria-labelledby="about-resources">
          <h2 id="about-resources">{text("関連情報", "Explore further")}</h2>
          <ul className="link-list">
            <li>
              <ExternalLink href={github_repository_url}>
                {text("ソースコード", "Source code")}
              </ExternalLink>
            </li>
            <li>
              <ExternalLink href={`${github_repository_url}/blob/main/UPDATE_HISTORY.md`}>
                {text("更新履歴", "Update history")}
              </ExternalLink>
            </li>
            <li>
              <ExternalLink href={`${github_repository_url}/tree/main/problems/v3`}>
                {text("問題データ・回答例", "Problem data and sample solutions")}
              </ExternalLink>
            </li>
            <li>
              <ExternalLink href="https://b.ueda.tech/?page=00684">
                {text("シェル芸勉強会の問題一覧", "Shell-gei workshop problems")}
              </ExternalLink>
            </li>
          </ul>
          {(github_author_url || blog_url) && (
            <>
              <h3>{text("作者", "Author")}</h3>
              <ul className="link-list">
                {github_author_url && (
                  <li>
                    <ExternalLink href={github_author_url}>GitHub / YusukeKato</ExternalLink>
                  </li>
                )}
                {blog_url && (
                  <li>
                    <ExternalLink href={blog_url}>Blog / yusukekato.jp</ExternalLink>
                  </li>
                )}
              </ul>
            </>
          )}
        </section>

        <section className="panel about-section" aria-labelledby="about-thanks">
          <h2 id="about-thanks">{text("謝辞", "Acknowledgments")}</h2>
          <ul className="link-list">
            <li>
              <ExternalLink href="https://github.com/jiro4989/websh">websh</ExternalLink>
              <p className="muted">
                {text("システム構成を参考にしています。", "Inspired the system architecture.")}
              </p>
            </li>
            <li>
              <ExternalLink href="https://github.com/ryuichiueda/ShellGeiData">
                ShellGeiData
              </ExternalLink>
              <p className="muted">{text("問題で利用しています。", "Used in the problems.")}</p>
            </li>
            <li>
              <ExternalLink href="https://github.com/theoremoon/ShellgeiBot-Image">
                ShellgeiBot-Image
              </ExternalLink>
              <p className="muted">
                {text("旧sandboxで利用していました。", "Used in the previous sandbox.")}
              </p>
            </li>
            <li>
              <ExternalLink href="https://gist.github.com/eggplants/71c0459f38028938a15d35b19bab47b5">
                eggplants/ans.csv
              </ExternalLink>
              <p className="muted">
                {text(
                  "回答例のご提供に感謝します。",
                  "Thank you for contributing sample solutions.",
                )}
              </p>
            </li>
          </ul>
        </section>

        <section className="panel about-section" aria-labelledby="about-notice">
          <h2 id="about-notice">{text("利用上の注意", "Usage notes")}</h2>
          <p>
            {text(
              "このウェブサイトの利用によって生じる損害等について一切責任を負いません。",
              "We are not responsible for any damages caused by the use of this website.",
            )}
          </p>
        </section>
      </div>
    </div>
  );
};

export default AboutPage;
