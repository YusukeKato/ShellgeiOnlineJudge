import React from "react";
import "../css/header.css";

const SojHeader: React.FC = () => {
  return (
    <>
      <header>
        <h1 className="soj-header" data-label="SHELLGEI ONLINE JUDGE">
          シェル・ワンライナーの遊び場 / Shell One-Liner Playground
        </h1>
      </header>
    </>
  );
};

export default SojHeader;
