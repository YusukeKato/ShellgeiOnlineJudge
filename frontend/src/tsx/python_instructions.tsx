import {
  buildPythonScript,
  buildPythonProblemScript,
  type SubmissionExampleProps,
} from "../functions/submission_examples";
import { useLanguage } from "../language";
import HelpDetails from "./help_details";
import CopyableCode from "./copyable_code";

export default function PythonInstructions(props: SubmissionExampleProps) {
  // 現在の入力・問題を送信し、応答JSONを読むPython 3の例を表示する。
  const { text } = useLanguage();
  return (
    <HelpDetails summary={text("Pythonスクリプトから実行する", "Run from a Python script")}>
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
      <h3>{text("問題データを取得する", "Get problem data")}</h3>
      <p>
        {text("次のスクリプトを ", "Save the following script as ")}
        <code>problems.py</code>
        {text(" として保存し、", " and run ")}
        <code>python3 problems.py</code>
        {text(
          " で実行してください。追加ライブラリなしで問題一覧と選択中の問題の詳細を取得します。一覧にはIDと日英のタイトル、詳細には日英の問題文・入力・想定出力・回答例が含まれます。",
          ". No additional libraries are needed. It fetches the problem list (IDs and Japanese/English titles) and the selected problem (statements in both languages, input, expected output and an example answer).",
        )}
      </p>
      <p>
        <code>detail["input"]</code>
        {text(" が input.txt の内容、", " is the content of input.txt, ")}
        <code>detail["expected_output"]</code>
        {text(" が想定出力、", " is the expected output, and ")}
        <code>detail["answer"]</code>
        {text(" が回答例です。", " is the example answer.")}
      </p>
      <CopyableCode
        value={buildPythonProblemScript(props)}
        copyLabel={text("Pythonスクリプトをコピー", "Copy Python script")}
      />
    </HelpDetails>
  );
}
