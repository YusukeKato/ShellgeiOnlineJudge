import React from "react";
import { updateProblem } from "../functions/update_problem";
import "../css/summary.css";
import "../css/headline.css";
import "../css/select.css";
import "../css/button.css";
import "../css/common.css";

interface SojValuesInterface {
  soj_url: string;
  selectedProblemImage: string;
  changeSelectedProblemImage: (event: React.ChangeEvent<HTMLSelectElement>) => void;
  setSelectedProblem: (value: string) => void;
  setProblemStatement: (value: string) => void;
  setProblemInput: (value: string) => void;
  setProblemOutput: (value: string) => void;
}

const SojSelectImage: React.FC<SojValuesInterface> = ({
  soj_url,
  selectedProblemImage,
  changeSelectedProblemImage,
  setSelectedProblem,
  setProblemStatement,
  setProblemInput,
  setProblemOutput,
}) => {
  const SelectClick = () => {
    setSelectedProblem(selectedProblemImage);
    updateProblem(
      soj_url,
      selectedProblemImage,
      setProblemStatement,
      setProblemInput,
      setProblemOutput,
    );
  };
  return (
    <div className="soj-main">
      <h3>画像問題 / IMAGE PROBLEMS</h3>
      <div className="soj-centering">
        <label className="selectbox">
          <select
            value={selectedProblemImage}
            id="select-form-image"
            onChange={changeSelectedProblemImage}
          >
            <option value="IMAGE-00000001">1: 画像テスト</option>
            <option value="IMAGE-00000002">2: 横線</option>
            <option value="IMAGE-00000003">3: 円</option>
            <option value="IMAGE-00000004">4: 市松模様</option>
            <option value="IMAGE-00000005">5: 四角</option>
          </select>
        </label>
        <input
          type="button"
          value="決定 / SELECT"
          className="select-button"
          id="select-button-image"
          onClick={SelectClick}
        />
      </div>
    </div>
  );
};

export default SojSelectImage;
