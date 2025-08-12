import React from "react";
import "./image.css";
import black_tree_icon from "./BlackTreeIcon.jpg";

const SojLogo: React.FC = () => {
  return (
    <div className="image-centering">
      <img src={black_tree_icon} className="soj-image" alt="BlackTreeIcon" />
    </div>
  );
};

export default SojLogo;
