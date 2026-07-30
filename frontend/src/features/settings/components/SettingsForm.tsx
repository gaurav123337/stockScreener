import { useForm, type FieldValues } from "react-hook-form";
import { Section } from "@/components/Section";
import { Button } from "@/components/ui/Button";
import { Card, CardTitle } from "@/components/ui/Card";
import { controlClass, helpTextClass } from "@/components/ui/styles";
import type { Settings, SettingsPatch } from "@/types/api";
import { SECTION_META, label } from "../settingsMeta";
import { buildSettingsPatch } from "../settingsPatch";
import { SettingsSectionCard } from "./SettingsSectionCard";

interface SettingsFormProps {
  current: Settings;
  defaults: Settings;
  saving: boolean;
  onSave: (patch: SettingsPatch) => void;
  onReset: () => void;
}

export function SettingsForm({ current, defaults, saving, onSave, onReset }: SettingsFormProps) {
  const { register, handleSubmit } = useForm<FieldValues>();
  const submit = handleSubmit((values) => onSave(buildSettingsPatch(values, current)));

  return (
    <form onSubmit={submit}>
      <Section
        title="Settings"
        sub="Tune how the screener behaves. Changes apply immediately and are saved. Use Reset to restore factory defaults."
      />
      {SECTION_META.map(([section, title, description]) => (
        <SettingsSectionCard
          key={section}
          section={section}
          title={title}
          description={description}
          current={current}
          defaults={defaults}
          register={register}
        />
      ))}
      <Card>
        <CardTitle>{label("default_universe")}</CardTitle>
        <p className={helpTextClass}>
          Stocks scanned when the Scan symbol box is left empty. Separate with spaces or commas.
        </p>
        <textarea
          className={controlClass}
          rows={4}
          defaultValue={current.default_universe.join(" ")}
          {...register("default_universe")}
        />
        <p className="mt-1.5 text-xs text-muted">
          Default: {defaults.default_universe.length} Nifty-50 stocks
        </p>
      </Card>
      <div className="flex flex-col gap-3 sm:flex-row">
        <Button type="submit" disabled={saving}>
          Save changes
        </Button>
        <Button
          type="button"
          variant="secondary"
          disabled={saving}
          onClick={() => {
            if (window.confirm("Reset all settings to factory defaults?")) onReset();
          }}
        >
          Reset to default
        </Button>
      </div>
    </form>
  );
}
