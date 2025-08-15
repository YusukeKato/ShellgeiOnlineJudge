import React from "react";
import { submit } from "../functions/submit";
import "../css/code.css";
import "../css/button.css";
import "../css/common.css";
import blue_image from "../images/Blue.jpg";
import sample_gif from "../images/sample.gif";

interface SojValuesInterface {
  shellgei_limit: number;
  default_image: string;
  soj_url: string;
  inputShellgei: string;
  changeInputShellgei: (event: React.ChangeEvent<HTMLTextAreaElement>) => void;
  selectedProblem: string;
  setOutputResult: (value: string) => void;
  setJudgeResult: (value: string) => void;
  setImageResult: (value: string) => void;
  setUserShellgeiStatus: (value: string) => void;
}

const SojRun: React.FC<SojValuesInterface> = ({
  shellgei_limit,
  default_image,
  soj_url,
  inputShellgei,
  changeInputShellgei,
  selectedProblem,
  setOutputResult,
  setJudgeResult,
  setImageResult,
  setUserShellgeiStatus,
}) => {
  const SubmitClick = () => {
    submit(
      shellgei_limit,
      default_image,
      soj_url,
      inputShellgei,
      selectedProblem,
      setOutputResult,
      setJudgeResult,
      setImageResult,
      setUserShellgeiStatus,
    );
  };
  return (
    <div className="soj-main">
      <h2>実行 / RUN</h2>
      <details>
        <summary>注意点 / NOTES</summary>
        <h4>注意点 / NOTES</h4>
        <ul>
          <li>入力の取得 / Get Input : "cat input.txt"</li>
          <li>画像の出力先 / Output Image file : "media/output.jpg"</li>
          <li>GIF画像の出力先 / Output GIF Image file : "media/output.gif"</li>
          <li>
            出力は想定出力&想定画像と一致すること / The output must match the expected output and
            expected image.
          </li>
          <li>危険なシェル芸（危険シェル芸）は禁止 / Dangerous shell-gei are prohibited.</li>
          <li>
            余計な空白や改行は正誤判定に影響する可能性あり / Extra spaces and line breaks may affect
            the correctness judgment.
          </li>
        </ul>
        <h4>実行制限 / EXECUTION LIMITS</h4>
        <ul>
          <li>実行時間 / Execution Time : 10.0s</li>
          <li>入出力文字数 / Input/Output Size : 1000</li>
        </ul>
        <h4>実行環境 / EXECUTION ENVIRONMENT</h4>
        <ul>
          <li>cat /etc/os-release</li>
          <li>echo $SHELL</li>
          <li>bash --version</li>
          <li>python3 -V</li>
        </ul>
      </details>
      <details>
        <summary>シェル芸例 / EXAMPLES SHELLGEI</summary>
        <p>Example 1: Simple arithmetic</p>
        <div className="code-block">
          <pre>
            <code className="code-font">seq 10 | paste -s -d+ | bc # Output: 55</code>
          </pre>
        </div>
        <p>Example 2: Output Image</p>
        <div className="code-block">
          <pre>
            <code className="code-font">convert -size 200x200 xc:#0000AA media/output.jpg</code>
          </pre>
        </div>
        <div className="soj-centering">
          <img className="soj-image" src={blue_image} id="blue-image" alt="blue-image" />
        </div>
        <p>Example 3: Output GIF Image</p>
        <div className="code-block">
          <pre>
            <code className="code-font">
              seq 0 9 | xargs -I@ textimg @ -F100 -o @.jpg; convert -delay 10 *.jpg media/output.gif
            </code>
          </pre>
        </div>
        <div className="soj-centering">
          <img className="soj-image" src={sample_gif} id="sample-gif" alt="sample-gif" />
        </div>
      </details>
      <div className="soj-centering">
        <textarea
          value={inputShellgei}
          onChange={changeInputShellgei}
          cols={50}
          rows={12}
          id="cmdline"
          placeholder="ここにシェル芸を入力... / Input your shell-gei here..."
        ></textarea>
        <input
          type="button"
          value="実行 / RUN"
          className="run-button"
          id="submit-button"
          onClick={SubmitClick}
        />
      </div>
    </div>
  );
};

export default SojRun;
