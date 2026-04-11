import { useState, useEffect } from "react";

const CLASS = "dark-mode";
const KEY = "theme";

function getInitial(): boolean {
  const stored = localStorage.getItem(KEY);
  if (stored !== null) return stored === "dark";
  return window.matchMedia("(prefers-color-scheme: dark)").matches;
}

export function useDarkMode() {
  const [dark, setDark] = useState(getInitial);

  useEffect(() => {
    const html = document.documentElement;
    html.style.transition = "background-color 0.2s ease, color 0.2s ease";
    if (dark) {
      html.classList.add(CLASS);
      localStorage.setItem(KEY, "dark");
    } else {
      html.classList.remove(CLASS);
      localStorage.setItem(KEY, "light");
    }
  }, [dark]);

  return { dark, toggle: () => setDark(d => !d) };
}
