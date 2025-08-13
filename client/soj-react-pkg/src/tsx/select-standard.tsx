import React from "react";
import { updateProblem } from "../scripts/select_button";
import "../css/summary.css";
import "../css/headline.css";
import "../css/select.css";
import "../css/button.css";
import "../css/common.css";

interface SojValuesInterface {
  soj_url: string;
  selectedValue: string;
  handleSelectChange: (event: React.ChangeEvent<HTMLSelectElement>) => void;
  setSelectedProblem: (value: string) => void;
  setProblemStatement: (value: string) => void;
  setProblemInput: (value: string) => void;
  setProblemOutput: (value: string) => void;
}

const SojSelectStandard: React.FC<SojValuesInterface> = ({
  soj_url,
  selectedValue,
  handleSelectChange,
  setSelectedProblem,
  setProblemStatement,
  setProblemInput,
  setProblemOutput,
}) => {
  const SelectClick = () => {
    setSelectedProblem(selectedValue);
    updateProblem(soj_url, selectedValue, setProblemStatement, setProblemInput, setProblemOutput);
  };
  return (
    <div className="soj-main">
      <h2>問題選択 / SELECT PROBLEMS</h2>
      <h3>通常問題 / STANDARD PROBLEMS</h3>
      <div className="soj-centering">
        <label className="selectbox">
          <select value={selectedValue} id="select-form-standard" onChange={handleSelectChange}>
            <option value="GENERAL-00000001">1 : 出力テスト / Output Test</option>
            <option value="GENERAL-00000002">2 : 入力テスト / Input Test</option>
            <option value="GENERAL-00000003">3 : 改行テスト / Newline Test</option>
            <option value="GENERAL-00000004">4 : 足し算 / Addition</option>
            <option value="GENERAL-00000005">5 : フィボナッチ数列 / Fibonacci Sequence</option>
            <option value="GENERAL-00000006">6 : 円周率10桁 / Pi to 10 Digits</option>
            <option value="GENERAL-00000007">7 : 円周率100桁 / Pi to 100 Digits</option>
            <option value="GENERAL-00000008">8 : 鶴亀算 / Crane and Tortoise Problem</option>
            <option value="GENERAL-00000009">9 : 日記の並べ替え / Diary Rearrangement</option>
            <option value="GENERAL-00000010">10 : 虫食い日記 / Incomplete Diary</option>
            <option value="GENERAL-00000011">11 : 行列の回転 / Matrix Rotation</option>
            <option value="GENERAL-00000012">12 : ビットの反転 / Bit Reversal</option>
            <option value="GENERAL-00000013">
              13 : アルファベットの調査 / Alphabet Investigation
            </option>
            <option value="GENERAL-00000014">14 : グループ分け / Grouping</option>
            <option value="GENERAL-00000015">15 : 素数判定 / Prime Number Test</option>
            <option value="GENERAL-00000016">16 : HTMLテスト / HTML Test</option>
            <option value="GENERAL-00000017">17 : ソート1 / Sort 1</option>
            <option value="GENERAL-00000018">18 : 二分探索 / Binary Search</option>
            <option value="GENERAL-00000019">19 : 元の文字列 / Original String</option>
            <option value="GENERAL-00000020">20 : 素因数分解 / Prime Factorization</option>
            <option value="GENERAL-00000021">21 : 回文判定 / Palindrome Test</option>
            <option value="GENERAL-00000022">22 : 2の1024乗 / 2 to the 1024th Power</option>
            <option value="GENERAL-00000023">23 : スコア計算 / Score Calculation</option>
            <option value="GENERAL-00000024">24 : ナップサック問題 / Knapsack Problem</option>
            <option value="GENERAL-00000025">25 : 文字列の組み合わせ / String Combination</option>
            <option value="GENERAL-00000026">26 : 最短経路探索 / Shortest Path Search</option>
            <option value="GENERAL-00000027">27 : 電車の乗り換え / Train Transfer</option>
            <option value="GENERAL-00000028">28 : 模様の描画1 / Pattern Drawing 1</option>
            <option value="GENERAL-00000029">29 : 模様の描画2 / Pattern Drawing 2</option>
            <option value="GENERAL-00000030">30 : シーザー暗号 / Caesar Cipher</option>
            <option value="GENERAL-00000031">31 : 最大公約数 / Greatest Common Divisor</option>
            <option value="GENERAL-00000032">32 : 最小公倍数 / Least Common Multiple</option>
            <option value="GENERAL-00000033">33 : 文字カウント1 / Character Count 1</option>
            <option value="GENERAL-00000034">34 : xの5乗 / x to the 5th Power</option>
            <option value="GENERAL-00000035">35 : 文字列の複製 / Copy Strings</option>
            <option value="GENERAL-00000036">36 : NをN回出力 / Output N N times</option>
            <option value="GENERAL-00000037">37 : 数字の抽出 / Extract Numbers</option>
            <option value="GENERAL-00000038">38 : 割り算判定 / Division Test</option>
            <option value="GENERAL-00000039">39 : 重複削除 / Remove Duplicates</option>
            <option value="GENERAL-00000040">40 : 文字カウント2 / Character Count 2</option>
            <option value="GENERAL-00000041">41 : 魔法陣3x3 / Magic Square 3x3</option>
            <option value="GENERAL-00000042">42 : 魔法陣5x5 / Magic Square 5x5</option>
            <option value="GENERAL-00000043">43 : 文字列の複製2 / Copy Strings 2</option>
            <option value="GENERAL-00000044">44 : 文字列の検索 / String Search</option>
            <option value="GENERAL-00000045">45 : 模様の描画3 / Pattern Drawing 3</option>
            <option value="GENERAL-00000046">
              46 : 単位行列の生成 / Identity Matrix Generation
            </option>
            <option value="GENERAL-00000047">47 : IPアドレスの抽出 / Extract IP Address</option>
            <option value="GENERAL-00000048">48 : 文字列の圧縮 / String Compression</option>
            <option value="GENERAL-00000049">
              49 : 最大文字数の回文調査 / Maximum Length Palindrome Check
            </option>
            <option value="GENERAL-00000050">50 : 四則演算 / Four Arithmetic Operations</option>
          </select>
        </label>
        <input
          type="button"
          value="決定 / SELECT"
          className="select-button"
          id="select-button-standard"
          onClick={SelectClick}
        />
      </div>
    </div>
  );
};

export default SojSelectStandard;
