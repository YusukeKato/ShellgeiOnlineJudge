import React from "react";
import { updateProblem } from "../functions/update_problem";
import "../css/summary.css";
import "../css/headline.css";
import "../css/select.css";
import "../css/button.css";
import "../css/common.css";

interface SojValuesInterface {
  soj_url: string;
  selectedProblemPractice: string;
  changeSelectedProblemPractice: (event: React.ChangeEvent<HTMLSelectElement>) => void;
  setSelectedProblem: (value: string) => void;
  setProblemStatement: (value: string) => void;
  setProblemInput: (value: string) => void;
  setProblemOutput: (value: string) => void;
  setProblemImage: (value: string) => void;
}

const SojSelectPractice: React.FC<SojValuesInterface> = ({
  soj_url,
  selectedProblemPractice,
  changeSelectedProblemPractice,
  setSelectedProblem,
  setProblemStatement,
  setProblemInput,
  setProblemOutput,
  setProblemImage,
}) => {
  const SelectClick = () => {
    setSelectedProblem(selectedProblemPractice);
    updateProblem(
      soj_url,
      selectedProblemPractice,
      setProblemStatement,
      setProblemInput,
      setProblemOutput,
      setProblemImage,
    );
  };
  return (
    <div className="soj-main">
      <h3>練習問題 / PRACTICE PROBLEMS</h3>
      <div className="soj-centering">
        <label className="selectbox">
          <select
            value={selectedProblemPractice}
            id="select-form-practice"
            onChange={changeSelectedProblemPractice}
          >
            <option value="PRACTICE-awk-01">awk 1</option>
            <option value="PRACTICE-awk-02">awk 2</option>
            <option value="PRACTICE-awk-03">awk 3</option>
            <option value="PRACTICE-awk-04">awk 4</option>
            <option value="PRACTICE-awk-05">awk 5</option>
            <option value="PRACTICE-awk-06">awk 6</option>
            <option value="PRACTICE-cat-01">cat 1</option>
            <option value="PRACTICE-cat-02">cat 2</option>
            <option value="PRACTICE-cat-03">cat 3</option>
            <option value="PRACTICE-cat-04">cat 4</option>
            <option value="PRACTICE-echo-01">echo 1</option>
            <option value="PRACTICE-echo-02">echo 2</option>
            <option value="PRACTICE-echo-03">echo 3</option>
            <option value="PRACTICE-find-01">find 1</option>
            <option value="PRACTICE-find-02">find 2</option>
            <option value="PRACTICE-find-03">find 3</option>
            <option value="PRACTICE-grep-01">grep 1</option>
            <option value="PRACTICE-grep-02">grep 2</option>
            <option value="PRACTICE-grep-03">grep 3</option>
            <option value="PRACTICE-grep-04">grep 4</option>
            <option value="PRACTICE-sed-01">sed 1</option>
            <option value="PRACTICE-sed-02">sed 2</option>
            <option value="PRACTICE-sed-03">sed 3</option>
            <option value="PRACTICE-sed-04">sed 4</option>
            <option value="PRACTICE-sed-05">sed 5</option>
            <option value="PRACTICE-sed-06">sed 6</option>
            <option value="PRACTICE-sort-01">sort 1</option>
            <option value="PRACTICE-sort-02">sort 2</option>
            <option value="PRACTICE-sort-03">sort 3</option>
            <option value="PRACTICE-uniq-01">uniq 1</option>
            <option value="PRACTICE-uniq-02">uniq 2</option>
            <option value="PRACTICE-wc-01">wc 1</option>
            <option value="PRACTICE-wc-02">wc 2</option>
            <option value="PRACTICE-wc-03">wc 3</option>
          </select>
        </label>
        <input
          type="button"
          value="決定 / SELECT"
          className="select-button"
          id="select-button-practice"
          onClick={SelectClick}
        />
      </div>
    </div>
  );
};

export default SojSelectPractice;
