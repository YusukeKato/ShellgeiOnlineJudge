import { useRef, useState } from "react";
import { useLanguage } from "../language";

interface CopyableCodeProps {
  value: string;
  copyLabel: string;
}

export default function CopyableCode({ value, copyLabel }: CopyableCodeProps) {
  // 表示したコードの全文だけをコピーし、実行やAPI提出は行わない。
  const { text } = useLanguage();
  const code = useRef<HTMLPreElement>(null);
  const [copyResult, setCopyResult] = useState<{
    value: string;
    status: "copied" | "failed";
  } | null>(null);
  const copyStatus = copyResult?.value === value ? copyResult.status : null;

  const copyCode = async () => {
    // Clipboard権限がない場合は表示中の例を選択し、手動コピーへ案内する。
    // 古いコピー処理が完了しても、変更後のコードをコピー済みとは表示しない。
    try {
      await navigator.clipboard.writeText(value);
      setCopyResult({ value, status: "copied" });
    } catch {
      if (code.current?.textContent === value) {
        const range = document.createRange();
        range.selectNodeContents(code.current);
        code.current.focus();
        const selection = window.getSelection();
        selection?.removeAllRanges();
        selection?.addRange(range);
      }
      setCopyResult({ value, status: "failed" });
    }
  };

  return (
    <>
      <pre className="code-output" tabIndex={0} ref={code}>
        <code>{value}</code>
      </pre>
      <div className="code-copy-actions">
        <button type="button" className="copy-command-button" onClick={() => void copyCode()}>
          {copyLabel}
        </button>
        <span role="status">
          {copyStatus === "copied" && text("コピーしました", "Copied")}
          {copyStatus === "failed" &&
            text(
              "自動コピーできませんでした。コードを選択してコピーしてください。",
              "Automatic copying failed. Select and copy the code manually.",
            )}
        </span>
      </div>
    </>
  );
}
