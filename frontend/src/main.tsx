import React from "react";
import ReactDOM from "react-dom/client";

import "./css/index.css";
import App from "./tsx/App";

const rootElement = document.getElementById("root");
if (rootElement === null) {
  throw new Error("root element was not found");
}

ReactDOM.createRoot(rootElement).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
