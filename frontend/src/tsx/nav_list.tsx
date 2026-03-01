import React from "react";
import "../css/nav_list.css";

interface SojUrlsInterface {
  x_url: string;
  github_repository_url: string;
  blog_url: string;
}

const SojNavList: React.FC<SojUrlsInterface> = ({ github_repository_url, blog_url }) => {
  return (
    <ul className="nav-list">
      <li className="nav-list-item">
        <a href={github_repository_url} className="nav-list-button">
          GITHUB
        </a>
      </li>
      <li className="nav-list-item">
        <a href={github_repository_url + "UPDATE_HISTORY.md"} className="nav-list-button">
          HISTORY
        </a>
      </li>
      <li className="nav-list-item">
        <a href={blog_url + "/html/2025/0102.html"} className="nav-list-button">
          YK-BLOG
        </a>
      </li>
    </ul>
  );
};

export default SojNavList;
