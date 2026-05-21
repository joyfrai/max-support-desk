import React from "react";
import { createRoot } from "react-dom/client";
import { SupportDeskApp } from "./SupportDeskApp";

const rootElement = document.getElementById("support-desk-root");

if (rootElement) {
  createRoot(rootElement).render(
    <React.StrictMode>
      <SupportDeskApp />
    </React.StrictMode>
  );
}

