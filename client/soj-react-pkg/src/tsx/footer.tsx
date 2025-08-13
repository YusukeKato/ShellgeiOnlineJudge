import React from "react";
import "../css/footer.css";
import "../css/link.css";

const SojFooter: React.FC = () => {
  return (
    <>
      <h1 className="soj-footer" data-label="">
        GitHub -{" "}
        <a
          href="https://github.com/YusukeKato/ShellgeiOnlineJudge/discussions"
          className="white-link"
        >
          SHELLGEI ONLINE JUDGE Discussions
        </a>
        <br />
        &copy; 2023 YusukeKato All rights reserved.
      </h1>
    </>
  );
};

export default SojFooter;
