import {
  buildCurlCommand,
  buildCurlProblemCommands,
  type SubmissionExampleProps,
} from "../functions/submission_examples";
import { useLanguage } from "../language";
import HelpDetails from "./help_details";
import CopyableCode from "./copyable_code";

export default function CurlInstructions(props: SubmissionExampleProps) {
  // 現在の入力・問題に対応するcurl例とコピー操作を表示する。
  const { text } = useLanguage();
  return (
    <HelpDetails summary={text("ターミナルから実行する（curl）", "Run from your terminal (curl)")}>
      <p>
        {text(
          "下のコマンド全体をコピーして、Bashのターミナルに貼り付けて実行してください。サーバー上で実行した結果と判定がJSONで返ります。",
          "Copy the entire command below and run it in a Bash terminal. The server returns the execution result and verdict as JSON.",
        )}
      </p>
      <p>
        {text(
          "入力欄のコマンドと選択中の問題を反映しています。入力欄が空の場合はサンプルを表示します。",
          "The command uses your current input and selected problem. An example is shown when the editor is empty.",
        )}
      </p>
      <CopyableCode
        value={buildCurlCommand(props)}
        copyLabel={text("curlコマンドをコピー", "Copy curl command")}
      />
      <h3>{text("問題データを取得する", "Get problem data")}</h3>
      <p>
        {text(
          "次のコマンドでは、問題一覧と選択中の問題の詳細をJSONで取得します。一覧にはIDと日英のタイトル、詳細には日英の問題文・入力・想定出力・回答例が含まれます。",
          "The following commands fetch the problem list and the selected problem as JSON. The list includes IDs and Japanese/English titles. Details include statements in both languages, input, expected output and an example answer.",
        )}
      </p>
      <p>
        <code>input</code>
        {text(" が input.txt の内容、", " is the content of input.txt, ")}
        <code>expected_output</code>
        {text(" が想定出力、", " is the expected output, and ")}
        <code>answer</code>
        {text(" が回答例です。", " is the example answer.")}
      </p>
      <CopyableCode
        value={buildCurlProblemCommands(props)}
        copyLabel={text("curlコマンドをコピー", "Copy curl command")}
      />
    </HelpDetails>
  );
}
