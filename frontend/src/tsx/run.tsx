import React, { useEffect, useRef } from "react";
import { prepareSubmission, submit, SubmissionState } from "../functions/submit";
import "../css/code.css";
import "../css/button.css";
import "../css/common.css";
import blue_image from "../images/Blue.jpg";
import sample_gif from "../images/sample.gif";

interface SojValuesInterface {
  shellgei_limit: number;
  soj_url: string;
  inputShellgei: string;
  changeInputShellgei: (event: React.ChangeEvent<HTMLTextAreaElement>) => void;
  selectedProblem: string;
  submissionState: SubmissionState;
  setSubmissionState: React.Dispatch<React.SetStateAction<SubmissionState>>;
}

interface ActiveSubmission {
  controller: AbortController;
  requestKey: string;
  version: number;
}

const SojRun: React.FC<SojValuesInterface> = ({
  shellgei_limit,
  soj_url,
  inputShellgei,
  changeInputShellgei,
  selectedProblem,
  submissionState,
  setSubmissionState,
}) => {
  const submissionVersion = useRef(0);
  const activeSubmission = useRef<ActiveSubmission | null>(null);

  useEffect(() => {
    return () => {
      // unmount時に進行中の提出をabortし、破棄済みcomponentへ結果を反映しない。
      submissionVersion.current += 1;
      activeSubmission.current?.controller.abort();
      activeSubmission.current = null;
    };
  }, []);

  const submitClick = () => {
    // 入力を検証し、同一提出は無視する。異なる新規提出は旧通信をabortして最新結果だけを反映する。
    const prepared = prepareSubmission(shellgei_limit, inputShellgei, selectedProblem);
    if (prepared.kind === "validation_error") {
      submissionVersion.current += 1;
      activeSubmission.current?.controller.abort();
      activeSubmission.current = null;
      setSubmissionState(prepared);
      return;
    }
    if (activeSubmission.current?.requestKey === prepared.requestKey) {
      return;
    }
    activeSubmission.current?.controller.abort();
    const controller = new AbortController();
    const version = ++submissionVersion.current;
    activeSubmission.current = {
      controller,
      requestKey: prepared.requestKey,
      version,
    };
    setSubmissionState(prepared);
    void submit(soj_url, prepared, controller.signal).then((result) => {
      // abortを無視するfetchが遅れて完了しても、最新versionと一致する結果だけを採用する。
      if (version !== submissionVersion.current) {
        return;
      }
      activeSubmission.current = null;
      setSubmissionState(result);
    });
  };
  // ctrl + Enter で実行
  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.ctrlKey && e.key === "Enter") {
      e.preventDefault();
      submitClick();
    }
  };
  return (
    <div className="soj-main">
      <h2>実行 / RUN</h2>
      <details>
        <summary>注意点 / IMPORTANT NOTES</summary>
        <h4>注意点 / IMPORTANT NOTES</h4>
        <ul>
          <li>入力の取得 / How to read input : "cat input.txt"</li>
          <li>画像の出力先 / Image output path : "media/output.jpg"</li>
          <li>GIF画像の出力先 / GIF Image output path : "media/output.gif"</li>
          <li>
            出力は想定出力&想定画像と一致すること / Your output must exactly match the expected
            output and image.
          </li>
          <li>
            危険なシェル芸（危険シェル芸）は禁止 / Malicious shell commands are strictly prohibited.
          </li>
          <li>
            余計な空白や改行は正誤判定に影響する可能性あり / Extra spaces and line breaks may affect
            the final verdict.
          </li>
        </ul>
        <h4>実行制限 / CONSTRAINTS</h4>
        <ul>
          <li>実行時間 / Time Limit : 10.0s</li>
          <li>入出力文字数 / I/O Size Limit : 1000 characters</li>
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
        <summary>シェル芸例 / EXAMPLES SHELL-GEI</summary>
        <p>Example 1: Calculating a Sum</p>
        <div className="code-block">
          <pre>
            <code className="code-font">seq 10 | paste -s -d+ | bc # Output: 55</code>
          </pre>
        </div>
        <p>Example 2: Generating an Image</p>
        <div className="code-block">
          <pre>
            <code className="code-font">
              textimg SOJ -F50 | convert -size 200x200 xc:#0000AA - -gravity center -composite
              media/output.jpg
            </code>
          </pre>
        </div>
        <div className="soj-centering">
          <img className="soj-image" src={blue_image} id="blue-image" alt="blue-image" />
        </div>
        <p>Example 3: Generating a GIF Image</p>
        <div className="code-block">
          <pre>
            <code className="code-font">
              seq 0 9 | xargs -I@ bash -c 'textimg "$1" -F100 | convert - miff:-' _ @ | convert
              -delay 10 miff:- media/output.gif
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
          onKeyDown={handleKeyDown}
          cols={50}
          rows={12}
          id="cmdline"
          placeholder="ここにシェル芸を入力... / Type your shell one-liner here..."
        ></textarea>
        <input
          type="button"
          value="実行 / RUN (Ctrl+Enter)"
          className="run-button"
          id="submit-button"
          aria-busy={submissionState.kind === "running"}
          onClick={submitClick}
        />
      </div>
    </div>
  );
};

export default SojRun;
