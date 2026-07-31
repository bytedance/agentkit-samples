import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import "./styles.css";

const root = createRoot(document.getElementById("root")!);
const pathname = window.location.pathname.replace(/\/+$/, "") || "/";

void (pathname === "/codex"
  ? import("./CodexApp").then(({ CodexApp }) => CodexApp)
  : import("./AdminApp").then(({ AdminApp }) => AdminApp)
).then((Surface) => {
  root.render(
    <StrictMode>
      <Surface />
    </StrictMode>,
  );
});
