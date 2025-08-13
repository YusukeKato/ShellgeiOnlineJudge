import React from "react";
import "./image.css";
import "./common.css";
import black_tree_icon from "./images/BlackTreeIcon.jpg";

const SojLogo: React.FC = () => {
  return (
    <div className="soj-centering">
      <img src={black_tree_icon} className="soj-image" alt="BlackTreeIcon" />
    </div>
  );
};

export default SojLogo;
