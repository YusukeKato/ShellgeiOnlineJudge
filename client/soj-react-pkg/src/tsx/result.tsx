import React from "react";
import "../css/code.css";
import "../css/button.css";
import "../css/image.css";
import "../css/common.css";

const SojResult: React.FC = () => {
  return (
    <div className="soj-main">
      <h2>結果 / RESULT</h2>
      <h3>正誤判定 / JUDGEMENT</h3>
      <div className="text-block">
        <pre>
          <code className="code-font" id="result-text">
            NULL
          </code>
        </pre>
      </div>
      <h3>出力結果 / OUTPUT RESULT</h3>
      <div className="text-block">
        <pre>
          <code className="code-font" id="user-output-text">
            NULL
          </code>
        </pre>
      </div>
      <h3>出力画像 / OUTPUT IMAGE</h3>
      <div className="soj-image" id="result-image">
        {/* insert output image */}
      </div>
      <h3>実行したシェル芸 / EXECUTED SHELLGEI</h3>
      <div className="text-block">
        <pre>
          <code className="code-font" id="shellgei-text">
            NULL
          </code>
        </pre>
      </div>
      <hr className="black-line" />
    </div>
  );
};

export default SojResult;
