import { buildPythonScript, type SubmissionExampleProps } from "../functions/submission_examples";
import { useLanguage } from "../language";
import CopyableCode from "./copyable_code";

export default function PythonInstructions(props: SubmissionExampleProps) {
  // 現在の入力・問題を送信し、応答JSONを読むPython 3の例を表示する。
  const { text } = useLanguage();
  return (
    <details className="help-details">
      <summary>{text("Pythonスクリプトから実行する", "Run from a Python script")}</summary>
      <p>
        {text("下のスクリプト全体をコピーして、", "Copy the entire script below into ")}
        <code>submit.py</code>
        {text("として保存し、", " and run ")}
        <code>python3 submit.py</code>
        {text(
          "で実行してください。追加ライブラリは不要です。",
          ". No additional libraries are needed.",
        )}
      </p>
      <p>
        {text(
          "入力欄のコマンドと選択中の問題を反映しています。入力欄が空の場合はサンプルを表示します。応答JSONを読み取り、判定・標準出力・標準エラーを表示します。",
          "The script uses your current input and selected problem, or an example when the editor is empty. It parses the response JSON and prints the verdict, stdout and stderr.",
        )}
      </p>
      <CopyableCode
        value={buildPythonScript(props)}
        copyLabel={text("Pythonスクリプトをコピー", "Copy Python script")}
      />
    </details>
  );
}
