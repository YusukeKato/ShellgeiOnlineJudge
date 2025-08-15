import React from "react";
import "../css/code.css";
import "../css/common.css";

interface SojValuesInterface {
  selectedProblem: string;
}

const SojSelected: React.FC<SojValuesInterface> = ({ selectedProblem }) => {
  return (
    <div className="soj-main">
      <h3>選択した問題 / SELECTED PROBLEM</h3>
      <div className="text-block">
        <pre>
          <code id="selected-text" className="code-font">
            {selectedProblem}
          </code>
        </pre>
      </div>
    </div>
  );
};

export default SojSelected;
