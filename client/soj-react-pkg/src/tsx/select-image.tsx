import React from "react";
import "../css/summary.css";
import "../css/headline.css";
import "../css/select.css";
import "../css/button.css";
import "../css/common.css";

const SojSelectImage: React.FC = () => {
  return (
    <div className="soj-main">
      <h3>画像問題 / IMAGE PROBLEMS</h3>
      <div className="soj-centering">
        <label className="selectbox">
          <select defaultValue="IMAGE-00000001" id="select-form-image">
            <option value="IMAGE-00000001">1: 画像テスト</option>
            <option value="IMAGE-00000002">2: 横線</option>
            <option value="IMAGE-00000003">3: 円</option>
            <option value="IMAGE-00000004">4: 市松模様</option>
            <option value="IMAGE-00000005">5: 四角</option>
          </select>
        </label>
        <table>
          <tbody>
            <tr>
              <td>
                <input type="button" value="<" className="one-step-button" id="select-pre-image" />
              </td>
              <td>
                <input
                  type="button"
                  value="決定 / SELECT"
                  className="main-button"
                  id="select-button-image"
                />
              </td>
              <td>
                <input type="button" value=">" className="one-step-button" id="select-next-image" />
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  );
};

export default SojSelectImage;
