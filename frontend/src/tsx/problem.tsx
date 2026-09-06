import React from "react";
import { ProblemDisplay } from "../functions/update_problem";
import { useLanguage } from "../language";

interface ProblemProps {
  problem: ProblemDisplay | null;
  error: string | null;
  selectedProblem: string;
}

const SojProblem: React.FC<ProblemProps> = ({ problem, error, selectedProblem }) => {
  // 問題文だけを表示言語で選び、判定に使う入出力は変換しない。
  const { language, text } = useLanguage();
  return (
    <section
      className="panel problem-panel"
      aria-labelledby="problem-heading"
      aria-busy={!problem && !error}
    >
      <div className="problem-meta">
        <span id="selected-text">{selectedProblem}</span>
      </div>
      <h2 id="problem-heading">{problem?.title[language] ?? text("問題", "Problem")}</h2>
      {error ? (
        <p className="result-error" role="alert" lang="en">
          {error}
        </p>
      ) : !problem ? (
        <p className="muted" role="status">
          {text("問題を読み込んでいます…", "Loading problem…")}
        </p>
      ) : (
        <>
          <p className="problem-statement" id="problem-text">
            {problem.statement[language]}
          </p>
          <div className="io-block">
            <h3 className="io-label">
              {text("入力", "Input")} <span>input.txt</span>
            </h3>
            <pre className="code-output" tabIndex={0}>
              <code id="input-text">{problem.input}</code>
            </pre>
          </div>
          <div className="io-block">
            <h3 className="io-label">{text("想定出力", "Expected output")}</h3>
            <pre className="code-output" tabIndex={0}>
              <code id="output-text">{problem.output}</code>
            </pre>
          </div>
          {selectedProblem.startsWith("IMAGE-") && (
            <div className="io-block">
              <h3 className="io-label">{text("想定画像", "Expected image")}</h3>
              <img
                className="image-output"
                src={problem.image}
                id="expected-image"
                alt={text("この問題の想定画像", "Expected image for this problem")}
              />
            </div>
          )}
        </>
      )}
    </section>
  );
};

export default SojProblem;
