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
}

const SojSelectPractice: React.FC<SojValuesInterface> = ({
  soj_url,
  selectedProblemPractice,
  changeSelectedProblemPractice,
  setSelectedProblem,
  setProblemStatement,
  setProblemInput,
  setProblemOutput,
}) => {
  const SelectClick = () => {
    setSelectedProblem(selectedProblemPractice);
    updateProblem(
      soj_url,
      selectedProblemPractice,
      setProblemStatement,
      setProblemInput,
      setProblemOutput,
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
            <option value="EXERCISE-awk-01">awk 1</option>
            <option value="EXERCISE-awk-02">awk 2</option>
            <option value="EXERCISE-awk-03">awk 3</option>
            <option value="EXERCISE-awk-04">awk 4</option>
            <option value="EXERCISE-awk-05">awk 5</option>
            <option value="EXERCISE-awk-06">awk 6</option>
            <option value="EXERCISE-cat-01">cat 1</option>
            <option value="EXERCISE-cat-02">cat 2</option>
            <option value="EXERCISE-cat-03">cat 3</option>
            <option value="EXERCISE-cat-04">cat 4</option>
            <option value="EXERCISE-echo-01">echo 1</option>
            <option value="EXERCISE-echo-02">echo 2</option>
            <option value="EXERCISE-echo-03">echo 3</option>
            <option value="EXERCISE-find-01">find 1</option>
            <option value="EXERCISE-find-02">find 2</option>
            <option value="EXERCISE-find-03">find 3</option>
            <option value="EXERCISE-grep-01">grep 1</option>
            <option value="EXERCISE-grep-02">grep 2</option>
            <option value="EXERCISE-grep-03">grep 3</option>
            <option value="EXERCISE-grep-04">grep 4</option>
            <option value="EXERCISE-sed-01">sed 1</option>
            <option value="EXERCISE-sed-02">sed 2</option>
            <option value="EXERCISE-sed-03">sed 3</option>
            <option value="EXERCISE-sed-04">sed 4</option>
            <option value="EXERCISE-sed-05">sed 5</option>
            <option value="EXERCISE-sed-06">sed 6</option>
            <option value="EXERCISE-sort-01">sort 1</option>
            <option value="EXERCISE-sort-02">sort 2</option>
            <option value="EXERCISE-sort-03">sort 3</option>
            <option value="EXERCISE-uniq-01">uniq 1</option>
            <option value="EXERCISE-uniq-02">uniq 2</option>
            <option value="EXERCISE-wc-01">wc 1</option>
            <option value="EXERCISE-wc-02">wc 2</option>
            <option value="EXERCISE-wc-03">wc 3</option>
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
