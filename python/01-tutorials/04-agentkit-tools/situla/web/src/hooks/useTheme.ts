import { useEffect, useState } from "react";
import type { Theme } from "../ui-types";

function readInitialTheme(): Theme {
  try {
    return window.localStorage.getItem("situla-theme") === "light" ? "light" : "dark";
  } catch {
    return "dark";
  }
}

export function useTheme() {
  const [theme, setTheme] = useState<Theme>(readInitialTheme);

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    document.documentElement.style.colorScheme = theme;
    document.querySelector<HTMLMetaElement>('meta[name="theme-color"]')?.setAttribute(
      "content",
      theme === "light" ? "#f5f7fb" : "#0b0e14",
    );
    try {
      window.localStorage.setItem("situla-theme", theme);
    } catch {
      // Theme persistence is optional when storage is unavailable.
    }
  }, [theme]);

  return {
    theme,
    toggleTheme: () => setTheme((current) => current === "dark" ? "light" : "dark"),
  };
}
