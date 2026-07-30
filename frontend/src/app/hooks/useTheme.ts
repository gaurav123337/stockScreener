import { useCallback, useState } from "react";

export type Theme = "light" | "dark";

const THEME_STORAGE_KEY = "stockscreener-theme";
const THEME_COLORS: Record<Theme, string> = {
  light: "#f4f7fb",
  dark: "#07111f",
};

function isTheme(value: string | null): value is Theme {
  return value === "light" || value === "dark";
}

function getStoredTheme(): Theme | null {
  try {
    const value = localStorage.getItem(THEME_STORAGE_KEY);
    return isTheme(value) ? value : null;
  } catch {
    return null;
  }
}

function getSystemTheme(): Theme {
  return window.matchMedia?.("(prefers-color-scheme: light)").matches ? "light" : "dark";
}

function applyTheme(theme: Theme) {
  const root = document.documentElement;
  root.classList.toggle("light", theme === "light");
  root.classList.toggle("dark", theme === "dark");
  root.style.colorScheme = theme;

  document.querySelector('meta[name="theme-color"]')?.setAttribute("content", THEME_COLORS[theme]);
}

export function initializeTheme(): Theme {
  const theme = getStoredTheme() ?? getSystemTheme();
  applyTheme(theme);
  return theme;
}

export function useTheme() {
  const [theme, setTheme] = useState<Theme>(() =>
    document.documentElement.classList.contains("light") ? "light" : "dark",
  );

  const toggleTheme = useCallback(() => {
    setTheme((currentTheme) => {
      const nextTheme = currentTheme === "dark" ? "light" : "dark";
      applyTheme(nextTheme);

      try {
        localStorage.setItem(THEME_STORAGE_KEY, nextTheme);
      } catch {
        // The visual preference still applies when browser storage is unavailable.
      }

      return nextTheme;
    });
  }, []);

  return { theme, toggleTheme };
}
