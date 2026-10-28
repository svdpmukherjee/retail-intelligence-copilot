import { useEffect, useState } from "react";

type Theme = "light" | "dark";

function systemTheme(): Theme {
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

// Sets data-theme on <html>; until the user toggles, CSS follows prefers-color-scheme.
export default function ThemeToggle() {
  const [theme, setTheme] = useState<Theme | null>(null);

  useEffect(() => {
    if (theme) document.documentElement.setAttribute("data-theme", theme);
  }, [theme]);

  const current = theme ?? systemTheme();
  const next: Theme = current === "dark" ? "light" : "dark";
  return (
    <button type="button" className="btn" onClick={() => setTheme(next)} aria-label={`Switch to ${next} theme`}>
      {next === "dark" ? "Dark" : "Light"} theme
    </button>
  );
}
