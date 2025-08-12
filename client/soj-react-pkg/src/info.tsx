import React from "react";
import "./headline.css";
import "./common.css";

interface SojInfoInterface {
  update_date: string;
  current_version: string;
}

const SojInfo: React.FC<SojInfoInterface> = ({ update_date, current_version }) => {
  return (
    <div className="soj-main">
      <h2>概要 / INFORMATION</h2>
      <h3>最終更新日 / LAST UPDATED</h3>
      <ul>
        <li>update: {update_date}</li>
        <li>version: {current_version}</li>
      </ul>
    </div>
  );
};

export default SojInfo;
