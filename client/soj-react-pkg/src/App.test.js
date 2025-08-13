import React from "react";
import { render, screen } from "@testing-library/react";
import App from "./tsx/App.tsx";

test("renders", () => {
  render(<App />);
  const linkElement = screen.getByText(/2023 YusukeKato All rights reserved./i);
  expect(linkElement).toBeInTheDocument();
});
