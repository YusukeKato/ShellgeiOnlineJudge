import React from "react";
import "../css/code.css";
import "../css/button.css";
import "../css/image.css";
import "../css/common.css";

interface SojValuesInterface {
  outputResult: string;
  judgeResult: string;
  imageResult: string;
  inputShellgei: string;
}

const SojResult: React.FC<SojValuesInterface> = ({
  outputResult,
  judgeResult,
  imageResult,
  inputShellgei,
}) => {
  return (
    <div className="soj-main">
      <h2>結果 / RESULT</h2>
      <h3>正誤判定 / JUDGEMENT</h3>
      <div className="text-block">
        <pre>
          <code className="code-font" id="result-text">
            {judgeResult}
          </code>
        </pre>
      </div>
      <h3>出力結果 / OUTPUT RESULT</h3>
      <div className="text-block">
        <pre>
          <code className="code-font" id="user-output-text">
            {outputResult}
          </code>
        </pre>
      </div>
      <h3>出力画像 / OUTPUT IMAGE</h3>
      <div className="soj-centering" id="result-image">
        <img className="soj-image" src={imageResult} id="result-image" alt="result-image" />
      </div>
      <h3>実行したシェル芸 / EXECUTED SHELLGEI</h3>
      <div className="text-block">
        <pre>
          <code className="code-font" id="shellgei-text">
            {inputShellgei}
          </code>
        </pre>
      </div>
      <hr className="black-line" />
    </div>
  );
};

export default SojResult;
