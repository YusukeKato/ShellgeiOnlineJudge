import React from "react";
import "../css/code.css";
import "../css/common.css";

interface SojValuesInterface {
  selectedValue: string;
}

const SojSelected: React.FC<SojValuesInterface> = ({ selectedValue }) => {
  return (
    <div className="soj-main">
      <h3>選択した問題 / SELECTED PROBLEM</h3>
      <div className="text-block">
        <pre>
          <code id="selected-text" className="code-font">
            {selectedValue}
          </code>
        </pre>
      </div>
    </div>
  );
};

export default SojSelected;
