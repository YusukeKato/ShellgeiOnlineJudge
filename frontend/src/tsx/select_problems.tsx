import React, { useState, useEffect, useRef } from "react";
import { getProblems } from "../api/client";
import { ProblemSummary } from "../api/types";
import { useLanguage } from "../language";

interface SojValuesInterface {
  soj_url: string;
  selectedProblem: string;
  onSelectProblem: (problemId: string) => void;
}

const SojSelectProblems: React.FC<SojValuesInterface> = ({
  soj_url,
  selectedProblem,
  onSelectProblem,
}) => {
  // 選択UIはnative detailsとbuttonを使い、タッチとキーボードで同じ操作を提供する。
  const { language, text } = useLanguage();
  const [activeTab, setActiveTab] = useState("STANDARD");
  const [problemList, setProblemList] = useState<ProblemSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const picker = useRef<HTMLDetailsElement>(null);
  const summary = useRef<HTMLElement>(null);

  useEffect(() => {
    // 一覧は言語切替で再取得しない。破棄後のstate更新も避ける。
    const controller = new AbortController();
    setLoading(true);
    setError(false);
    void getProblems(soj_url, { signal: controller.signal })
      .then((data) => {
        if (!controller.signal.aborted) {
          setProblemList(data);
          setLoading(false);
        }
      })
      .catch(() => {
        if (!controller.signal.aborted) {
          setError(true);
          setLoading(false);
        }
      });
    return () => controller.abort();
  }, [soj_url]);

  const selected = problemList.find((problem) => problem.id === selectedProblem);
  const selectedCategory = selected?.category ?? selectedProblem.split("-")[0];
  useEffect(() => {
    // 直接URL・戻る/進む・選択変更では該当カテゴリへ合わせ、タブだけの操作は保持する。
    setActiveTab(selectedCategory);
  }, [selectedProblem, selectedCategory]);
  const categories = [
    { id: "STANDARD", label: text("通常", "Standard") },
    { id: "PRACTICE", label: text("練習", "Practice") },
    { id: "IMAGE", label: text("画像", "Image") },
  ];
  const select = (id: string) => {
    // 折りたたみで選択buttonが隠れても、focusが失われないようsummaryへ戻す。
    onSelectProblem(id);
    if (picker.current) picker.current.open = false;
    summary.current?.focus();
  };

  return (
    <details className="problem-picker" ref={picker}>
      <summary className="picker-summary" ref={summary}>
        <span>{text("問題を選ぶ", "Choose problem")}</span>
        <span className="picker-current">
          {selected ? (language === "ja" ? selected.title_ja : selected.title_en) : selectedProblem}
        </span>
      </summary>
      <div
        className="category-tabs"
        role="group"
        aria-label={text("問題のカテゴリ", "Problem category")}
      >
        {categories.map((category) => (
          <button
            type="button"
            className="category-tab"
            aria-pressed={activeTab === category.id}
            key={category.id}
            onClick={() => setActiveTab(category.id)}
          >
            {category.label}
          </button>
        ))}
      </div>
      {loading && (
        <p className="muted" role="status">
          {text("問題一覧を読み込んでいます…", "Loading problems…")}
        </p>
      )}
      {error && (
        <p role="alert" className="result-error" lang="en">
          Error: Failed to load problems
        </p>
      )}
      <ul className="problem-list">
        {problemList
          .filter((problem) => problem.category === activeTab)
          .map((problem) => (
            <li key={problem.id}>
              <button
                type="button"
                className="problem-option"
                aria-current={selectedProblem === problem.id ? "true" : undefined}
                onClick={() => select(problem.id)}
              >
                <span className="problem-option-title">
                  {language === "ja" ? problem.title_ja : problem.title_en}
                </span>
                <span className="problem-option-id">{problem.id}</span>
              </button>
            </li>
          ))}
      </ul>
    </details>
  );
};

export default SojSelectProblems;
