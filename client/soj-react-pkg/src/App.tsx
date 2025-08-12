import React from "react";
import SojHeader from "./header";
import SojFooter from "./footer";
import SojLogo from "./logo";
import "./App.css";

const App: React.FC = () => {
  return (
    <div className="App">
      <header>
        <SojHeader />
      </header>
      <div className="soj-main">
        <SojLogo />
      </div>
      <footer>
        <SojFooter />
      </footer>
    </div>
  );
};

export default App;
