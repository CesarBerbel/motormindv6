import React from "react";
import { createRoot } from "react-dom/client";
import "./styles.css";
import { registerServiceWorker } from "./pwa/registerServiceWorker.js";
import App from "./App.jsx";
import { AuthProvider } from "./auth/AuthContext.jsx";
import ConfirmDialogProvider from "./components/ConfirmDialog.jsx";
import ErrorBoundary from "./components/ErrorBoundary.jsx";

createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <ErrorBoundary>
      <AuthProvider>
        <ConfirmDialogProvider>
          <App />
        </ConfirmDialogProvider>
      </AuthProvider>
    </ErrorBoundary>
  </React.StrictMode>
);

registerServiceWorker();
