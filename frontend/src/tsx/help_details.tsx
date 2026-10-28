import { useRef, type ReactNode } from "react";
import { useLanguage } from "../language";

interface HelpDetailsProps {
  summary: string;
  children: ReactNode;
}

export default function HelpDetails({ summary, children }: HelpDetailsProps) {
  // 標準のdetails操作を維持し、長い案内を末尾から閉じられるようにする。
  const { text } = useLanguage();
  const details = useRef<HTMLDetailsElement>(null);
  const heading = useRef<HTMLElement>(null);
  const close = () => {
    // 自分の欄だけを閉じ、次のキーボード操作を続けられる見出しへ戻す。
    if (details.current) details.current.open = false;
    heading.current?.focus();
  };

  return (
    <details className="help-details" ref={details}>
      <summary ref={heading}>{summary}</summary>
      {children}
      <button
        type="button"
        className="details-close-button"
        aria-label={text(`${summary}を閉じる`, `Close ${summary}`)}
        onClick={close}
      >
        {text("閉じる", "Close")}
      </button>
    </details>
  );
}
