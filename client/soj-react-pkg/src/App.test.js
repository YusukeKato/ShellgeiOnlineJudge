import React from "react";
import { render, screen } from "@testing-library/react";
import App from "./App.tsx";

test("renders header", () => {
  render(<App />);
  const linkElement = screen.getByText(/SHELLGEI ONLINE JUDGE/i);
  expect(linkElement).toBeInTheDocument();
});

test("renders footer", () => {
  render(<App />);
  const linkElement = screen.getByText(/2023 YusukeKato All rights reserved./i);
  expect(linkElement).toBeInTheDocument();
});
