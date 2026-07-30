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
          return (
            <label
              className="grid gap-2 py-3 sm:grid-cols-[minmax(0,1fr)_10rem] sm:items-center"
              key={key}
            >
              <span className="text-sm font-semibold text-slate-200">
                {label(key)}
                <span className="block text-xs font-normal text-muted">
                  default {String(defaultsData[key])}
                </span>
              </span>
              <input
                className={controlClass}
                type={isNumber ? "number" : "text"}
                step={isNumber ? "any" : undefined}
                defaultValue={String(value)}
                {...register(`${section}.${key}`)}
              />
            </label>
          );
        })}
      </div>
    </Card>
  );
}
