import React, { useState, useEffect } from "react";
import { getProblems } from "../api/client";
import { ProblemSummary } from "../api/types";
import "../css/summary.css";
import "../css/headline.css";
import "../css/common.css";
import "../css/table_tab.css";

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
  const [activeTab, setActiveTab] = useState<string>("STANDARD");
  const [problemList, setProblemList] = useState<ProblemSummary[]>([]);

  // 問題リストをAPI経由で取得
  useEffect(() => {
    const controller = new AbortController();
    const fetchProblems = async () => {
      // API clientで検証済みの問題一覧だけをstateへ設定し、不正responseは表示へ混入させない。
      try {
        setProblemList(await getProblems(soj_url, { signal: controller.signal }));
      } catch {
        if (!controller.signal.aborted) {
          console.error("Failed to fetch problem list");
        }
      }
    };
    void fetchProblems();
    return () => {
      // URL変更またはunmount時に一覧取得を中断し、破棄済みcomponentのstateを更新しない。
      controller.abort();
    };
  }, [soj_url]);

  // 問題行をクリックしたときの処理
  const handleSelectClick = (problemId: string) => {
    // 選択された問題IDを親へ通知し、親の世代管理下で問題詳細を取得する。
    onSelectProblem(problemId);
  };

  // アクティブなタブのカテゴリで絞り込み
  const filteredProblems = problemList.filter((p) => p.category === activeTab);

  return (
    <div className="soj-main">
      <h2>問題選択 / PROBLEM SELECTION</h2>

      {/* タブUI */}
      <div className="tab-container">
        <button
          className={`tab-button ${activeTab === "STANDARD" ? "active" : ""}`}
          onClick={() => setActiveTab("STANDARD")}
        >
          通常問題 / STANDARD
        </button>
        <button
          className={`tab-button ${activeTab === "PRACTICE" ? "active" : ""}`}
          onClick={() => setActiveTab("PRACTICE")}
        >
          練習問題 / PRACTICE
        </button>
        <button
          className={`tab-button ${activeTab === "IMAGE" ? "active" : ""}`}
          onClick={() => setActiveTab("IMAGE")}
        >
          画像問題 / IMAGE
        </button>
      </div>

      {/* テーブルUI */}
      <div className="table-container">
        <table className="problem-table">
          <thead>
            <tr>
              <th>ID</th>
              <th>問題名 / TITLE</th>
            </tr>
          </thead>
          <tbody>
            {filteredProblems.map((p) => {
              // YAMLにタイトルがない場合のフォールバック
              const titleJa = p.title_ja || "タイトル未設定";
              const titleEn = p.title_en || "Untitled";

              return (
                <tr
                  key={p.id}
                  onClick={() => handleSelectClick(p.id)}
                  className={selectedProblem === p.id ? "selected-row" : ""}
                >
                  <td className="col-id">{p.id}</td>
                  <td className="col-title">
                    {titleJa} / {titleEn}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
};

export default SojSelectProblems;
