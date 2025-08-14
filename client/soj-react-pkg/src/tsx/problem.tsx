import React from "react";
import "../css/code.css";
import "../css/image.css";
import "../css/common.css";

interface SojValuesInterface {
  problemStatement: string;
  problemInput: string;
  problemOutput: string;
  problemImage: string;
}

const SojProblem: React.FC<SojValuesInterface> = ({
  problemStatement,
  problemInput,
  problemOutput,
  problemImage,
}) => {
  return (
    <div className="soj-main">
      <h2>問題 / PROBLEM</h2>
      <h3>問題文 / STATEMENT</h3>
      <div className="text-block">
        <pre>
          <code className="code-font" id="problem-text">
            {problemStatement}
          </code>
        </pre>
      </div>
      <h3>入力 / INPUT</h3>
      <div className="text-block">
        <pre>
          <code className="code-font" id="input-text">
            {problemInput}
          </code>
        </pre>
      </div>
      <h3>想定出力 / EXPECTED OUTPUT</h3>
      <div className="text-block">
        <pre>
          <code className="code-font" id="output-text">
            {problemOutput}
          </code>
        </pre>
      </div>
      <h3>想定画像 / EXPECTED IMAGE</h3>
      <div className="soj-centering">
        <img className="soj-image" src={problemImage} id="expected-image" alt="expected-image" />
      </div>
    </div>
  );
};

export default SojProblem;
