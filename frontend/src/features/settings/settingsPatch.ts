import type { FieldValues } from "react-hook-form";
import type { Settings, SettingsPatch, SettingsSection } from "@/types/api";
import { SECTION_META } from "./settingsMeta";

/** Convert flat form values into the nested settings API patch. */
export function buildSettingsPatch(values: FieldValues, current: Settings): SettingsPatch {
  const patch: SettingsPatch = {};

  for (const [section] of SECTION_META) {
    const sectionData = current[section] as SettingsSection | undefined;
    if (!sectionData) continue;

    for (const [key, initial] of Object.entries(sectionData)) {
      if (Array.isArray(initial)) continue;
      const raw = values[`${section}.${key}`];
      if (raw === undefined || raw === null) continue;

      let value: unknown = raw;
      if (typeof initial === "number") {
        const numericValue = Number(raw);
        if (raw === "" || Number.isNaN(numericValue)) continue;
        value = numericValue;
      } else if (key === "allowed_extensions") {
        value = String(raw)
          .split(/[\s,]+/)
          .filter(Boolean);
      }

      (patch[section] as Record<string, unknown>) ??= {};
      (patch[section] as Record<string, unknown>)[key] = value;
    }
  }

  patch.default_universe = String(values.default_universe ?? "")
    .trim()
    .split(/[\s,]+/)
    .filter(Boolean)
    .map((symbol) => symbol.toUpperCase());

  return patch;
}
