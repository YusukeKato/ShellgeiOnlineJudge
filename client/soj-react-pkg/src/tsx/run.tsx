import React from "react";
import "../css/code.css";
import "../css/button.css";
import "../css/common.css";

interface SojValuesInterface {
  inputShellgei: string;
  changeInputShellgei: (event: React.ChangeEvent<HTMLTextAreaElement>) => void;
}

const SojRun: React.FC<SojValuesInterface> = ({ inputShellgei, changeInputShellgei }) => {
  return (
    <div className="soj-main">
      <h2>実行 / RUN</h2>
      <details>
        <summary>注意点 / NOTES</summary>
        <h4>注意点 / NOTES</h4>
        <ul>
          <li>入力の取得 / Get Input : "cat input.txt"</li>
          <li>画像の出力先 / Output Image file : "media/output.jpg"</li>
          <li>
            出力は想定出力&想定画像と一致すること / The output must match the expected output and
            expected image.
          </li>
          <li>危険なシェル芸（危険シェル芸）は禁止 / Dangerous shell tricks are prohibited.</li>
          <li>
            余計な空白や改行は正誤判定に影響する可能性あり / Extra spaces and line breaks may affect
            the correctness judgment.
          </li>
        </ul>
        <h4>実行制限 / EXECUTION LIMITS</h4>
        <ul>
          <li>実行時間 / Execution Time : 5.0s</li>
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
      <div className="soj-centering">
        <textarea
          value={inputShellgei}
          onChange={changeInputShellgei}
          cols={50}
          rows={12}
          id="cmdline"
          placeholder="ここにシェル芸を入力... / Input your shell-gei here..."
        ></textarea>
        <input type="button" value="実行 / RUN" className="run-button" id="submit-button" />
      </div>
    </div>
  );
};

export default SojRun;
