import React, { useState, useEffect } from "react";
import { updateProblem } from "../functions/update_problem";
import "../css/summary.css";
import "../css/headline.css";
import "../css/common.css";
import "../css/table_tab.css";

interface ProblemMeta {
  id: string;
  category: string;
  title_ja: string;
  title_en: string;
}

interface SojValuesInterface {
  soj_url: string;
  selectedProblem: string;
  setSelectedProblem: (value: string) => void;
  setProblemStatement: (value: string) => void;
  setProblemInput: (value: string) => void;
  setProblemOutput: (value: string) => void;
  setProblemImage: (value: string) => void;
}

const SojSelectProblems: React.FC<SojValuesInterface> = ({
  soj_url,
  selectedProblem,
  setSelectedProblem,
  setProblemStatement,
  setProblemInput,
  setProblemOutput,
  setProblemImage,
}) => {
  const [activeTab, setActiveTab] = useState<string>("STANDARD");
  const [problemList, setProblemList] = useState<ProblemMeta[]>([]);

  // 問題リストをAPI経由で取得
  useEffect(() => {
    const fetchProblems = async () => {
      try {
        const response = await fetch(`${soj_url}/api/problems`);
        if (response.ok) {
          const data = await response.json();
          setProblemList(data);
        }
      } catch (error) {
        console.error("Failed to fetch problem list:", error);
      }
    };
    fetchProblems();
  }, [soj_url]);

  // 問題行をクリックしたときの処理
  const handleSelectClick = (problemId: string) => {
    setSelectedProblem(problemId);
    updateProblem(
      soj_url,
      problemId,
      setProblemStatement,
      setProblemInput,
      setProblemOutput,
      setProblemImage,
    );
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
