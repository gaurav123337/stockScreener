import type { FieldValues, UseFormRegister } from "react-hook-form";
import { Card, CardTitle } from "@/components/ui/Card";
import { controlClass, helpTextClass } from "@/components/ui/styles";
import type { Settings, SettingsSection } from "@/types/api";
import { label } from "../settingsMeta";

interface SettingsSectionCardProps {
  section: string;
  title: string;
  description: string;
  current: Settings;
  defaults: Settings;
  register: UseFormRegister<FieldValues>;
}

export function SettingsSectionCard(props: SettingsSectionCardProps) {
  const { section, title, description, current, defaults, register } = props;
  const sectionData = (current[section] ?? {}) as SettingsSection;
  const defaultsData = (defaults[section] ?? {}) as SettingsSection;

  return (
    <Card>
      <CardTitle>{title}</CardTitle>
      <p className={helpTextClass}>{description}</p>
      <div className="mt-3 divide-y divide-border">
        {Object.entries(sectionData).map(([key, value]) => {
          if (Array.isArray(value)) return null;
          const isNumber = typeof value === "number";
          const isBoolean = typeof value === "boolean";
          return (
            <label
              className="grid gap-2 py-3 sm:grid-cols-[minmax(0,1fr)_10rem] sm:items-center"
              key={key}
            >
              <span className="text-sm font-semibold text-ink">
                {label(key)}
                <span className="block text-xs font-normal text-muted">
                  default {String(defaultsData[key])}
                </span>
              </span>
              {isBoolean ? (
                <span className="flex justify-start sm:justify-end">
                  <input
                    className="size-6 cursor-pointer appearance-none rounded-md border-2 border-muted bg-surface shadow-sm transition-colors checked:border-brand checked:bg-brand checked:bg-[url('data:image/svg+xml,%3Csvg_viewBox=%220_0_16_16%22_xmlns=%22http://www.w3.org/2000/svg%22%3E%3Cpath_d=%22m3_8_3_3_7-7%22_fill=%22none%22_stroke=%22white%22_stroke-linecap=%22round%22_stroke-linejoin=%22round%22_stroke-width=%222.5%22/%3E%3C/svg%3E')] checked:bg-center checked:bg-no-repeat hover:border-brand"
                    type="checkbox"
                    defaultChecked={value}
                    {...register(`${section}.${key}`)}
                  />
                </span>
              ) : (
                <input
                  className={controlClass}
                  type={isNumber ? "number" : "text"}
                  step={isNumber ? "any" : undefined}
                  defaultValue={String(value)}
                  {...register(`${section}.${key}`)}
                />
              )}
            </label>
          );
        })}
      </div>
    </Card>
  );
}
