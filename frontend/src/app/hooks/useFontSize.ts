import { useCallback, useState } from "react";

export const FONT_SIZE_MIN = 87.5;
export const FONT_SIZE_MAX = 125;
export const FONT_SIZE_STEP = 12.5;

const FONT_SIZE_STORAGE_KEY = "stockscreener-font-size";

function clampFontSize(value: number): number {
  return Math.min(FONT_SIZE_MAX, Math.max(FONT_SIZE_MIN, value));
}

function readStoredFontSize(): number {
  try {
    const stored = Number(localStorage.getItem(FONT_SIZE_STORAGE_KEY));
    return Number.isFinite(stored) ? clampFontSize(stored) : 100;
  } catch {
    return 100;
  }
}

function applyFontSize(value: number) {
  document.documentElement.style.fontSize = `${value}%`;
}

export function initializeFontSize(): number {
  const value = readStoredFontSize();
  applyFontSize(value);
  return value;
}

export function useFontSize() {
  const [fontSize, setFontSize] = useState(readStoredFontSize);

  const changeFontSize = useCallback((delta: number) => {
    setFontSize((current) => {
      const next = clampFontSize(current + delta);
      applyFontSize(next);
      try {
        localStorage.setItem(FONT_SIZE_STORAGE_KEY, String(next));
      } catch {
        // The visual preference still applies when browser storage is unavailable.
      }
      return next;
    });
  }, []);

  return {
    fontSize,
    increaseFontSize: () => changeFontSize(FONT_SIZE_STEP),
    decreaseFontSize: () => changeFontSize(-FONT_SIZE_STEP),
    canIncrease: fontSize < FONT_SIZE_MAX,
    canDecrease: fontSize > FONT_SIZE_MIN,
  };
}