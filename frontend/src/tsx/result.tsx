import React from "react";
import { submissionDisplay, SubmissionState } from "../functions/submit";
import "../css/code.css";
import "../css/button.css";
import "../css/image.css";
import "../css/common.css";

interface SojValuesInterface {
  submissionState: SubmissionState;
  defaultImage: string;
}

const SojResult: React.FC<SojValuesInterface> = ({ submissionState, defaultImage }) => {
  // 判別可能な提出stateを一度だけ表示modelへ変換し、field間で異なる世代の値が混ざるのを防ぐ。
  const display = submissionDisplay(submissionState, defaultImage);
  return (
    <div className="soj-main">
      <h2>結果 / RESULT</h2>
      <h3>正誤判定 / VERDICT</h3>
      <div className="text-block">
        <pre>
          <code className="code-font" id="result-text">
            {display.verdict}
          </code>
        </pre>
      </div>
      <h3>出力結果 / YOUR OUTPUT</h3>
      <div className="text-block">
        <pre>
          <code className="code-font" id="user-output-text">
            {display.output}
          </code>
        </pre>
      </div>
      <h3>出力画像 / OUTPUT IMAGE</h3>
      <div className="soj-centering" id="result-image">
        <img className="soj-image" src={display.image} id="result-image" alt="result-image" />
      </div>
      <h3>実行したシェル芸 / YOUR COMMAND</h3>
      <div className="text-block">
        <pre>
          <code className="code-font" id="shellgei-text">
            {display.commandStatus}
          </code>
        </pre>
      </div>
      <hr className="black-line" />
    </div>
  );
};

export default SojResult;
