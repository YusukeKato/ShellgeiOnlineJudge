import React, { useEffect, useRef } from "react";
import { prepareSubmission, submit, SubmissionState } from "../functions/submit";
import { useLanguage } from "../language";

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
  // 言語の変更は入力・提出の世代やAbortControllerを変更しない。
  const { text } = useLanguage();
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
    <section className="panel editor-panel" aria-labelledby="editor-heading">
      <div className="editor-toolbar">
        <h2 id="editor-heading">{text("コマンド", "Command")}</h2>
        <span className="muted">Bash</span>
      </div>
      <label htmlFor="cmdline" className="sr-only">
        {text("コマンドを入力", "Enter a command")}
      </label>
      <div className="editor-surface">
        <span className="editor-caption" aria-hidden="true">
          $
        </span>
        <textarea
          className="command-input"
          value={inputShellgei}
          onChange={changeInputShellgei}
          onKeyDown={handleKeyDown}
          rows={4}
          id="cmdline"
          spellCheck={false}
          autoCapitalize="off"
          autoCorrect="off"
          aria-describedby="command-limit"
          aria-invalid={inputShellgei.length > shellgei_limit}
          placeholder={text("ここにシェル芸を入力…", "Write your shell one-liner…")}
        />
      </div>
      <div className="run-toolbar">
        <span
          className="char-count"
          id="command-limit"
          data-over-limit={inputShellgei.length > shellgei_limit}
        >
          {inputShellgei.length} / {shellgei_limit} {text("文字", "characters")}
        </span>
        <button
          type="button"
          className="run-button"
          id="submit-button"
          aria-busy={submissionState.kind === "running"}
          onClick={submitClick}
        >
          {submissionState.kind === "running"
            ? text("実行中…", "Running…")
            : text("実行する", "Run command")}
          <span aria-hidden="true"> ↗</span>
        </button>
      </div>
      <p className="run-help">{text("Ctrl + Enter で実行", "Run with Ctrl + Enter")}</p>
      <details className="help-details">
        <summary>{text("使い方と実行条件", "Instructions & limits")}</summary>
        <ul>
          <li>
            {text("入力ファイル：", "Input file: ")}
            <code>cat input.txt</code>
          </li>
          <li>
            {text("画像問題の出力先：", "Image problem output: ")}
            <code>media/output.jpg</code>
          </li>
          <li>
            {text("GIFの表示用出力先：", "GIF preview output: ")}
            <code>media/output.gif</code>
          </li>
          <li>
            {text(
              "コマンドは1,000文字まで。実行時間の上限は10秒です。",
              "Commands can contain up to 1,000 characters. The time limit is 10 seconds.",
            )}
          </li>
          <li>
            {text(
              "空白や改行も判定に影響します。問題の想定出力を確認してください。",
              "Spaces and line breaks can affect the verdict. Check the expected output.",
            )}
          </li>
          <li>{text("危険なシェル芸は禁止です。", "Malicious shell commands are prohibited.")}</li>
          <li>
            {text(
              "画像は合計750KBまで。判定用画像を優先し、上限超過や読み取れないGIFは表示しません。",
              "Images share a 750KB limit. Judging images take priority; oversized or invalid GIFs are not displayed.",
            )}
          </li>
        </ul>
        <p>
          {text("環境の確認：", "Inspect the environment: ")}
          <code>cat /etc/os-release</code> / <code>bash --version</code>
        </p>
      </details>
      <details className="help-details">
        <summary>{text("コマンドの例", "Command examples")}</summary>
        <p>{text("1から10までの合計を求める", "Sum the numbers from 1 to 10")}</p>
        <pre className="code-output" tabIndex={0}>
          <code>seq 10 | paste -s -d+ | bc</code>
        </pre>
        <p>{text("画像問題で文字を画像にする", "Create a text image in an image problem")}</p>
        <pre className="code-output" tabIndex={0}>
          <code>textimg SOJ -F50 | convert - media/output.jpg</code>
        </pre>
        <p>{text("数字をアニメーションGIFにする", "Create an animated GIF of numbers")}</p>
        <pre className="code-output" tabIndex={0}>
          <code>{`seq 0 9 | xargs -I@ bash -c 'textimg "$1" -F100 | convert - miff:-' _ @ | convert -delay 10 miff:- media/output.gif`}</code>
        </pre>
      </details>
    </section>
  );
};

export default SojRun;
