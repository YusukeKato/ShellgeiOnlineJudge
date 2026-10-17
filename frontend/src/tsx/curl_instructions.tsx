import { buildCurlCommand, type SubmissionExampleProps } from "../functions/submission_examples";
import { useLanguage } from "../language";
import CopyableCode from "./copyable_code";

export default function CurlInstructions(props: SubmissionExampleProps) {
  // 現在の入力・問題に対応するcurl例とコピー操作を表示する。
  const { text } = useLanguage();
  return (
    <details className="help-details">
      <summary>{text("ターミナルから実行する（curl）", "Run from your terminal (curl)")}</summary>
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
    </details>
  );
}
