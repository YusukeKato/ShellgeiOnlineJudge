import React from "react";
import "./nav_list.css";
import "./interface/soj_info";

const SojNavList: React.FC<SojInfo> = ({ x_url, github_url, blog_url }) => {
  return (
    <ul className="nav-list">
      <li className="nav-list-item">
        <a href={x_url} className="nav-list-button">
          X(TWITTER)
        </a>
      </li>
      <li className="nav-list-item">
        <a href={github_url} className="nav-list-button">
          GITHUB
        </a>
      </li>
      <li className="nav-list-item">
        <a href={blog_url} className="nav-list-button">
          YK-BLOG
        </a>
      </li>
    </ul>
  );
};

export default SojNavList;
