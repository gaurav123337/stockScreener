import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useForm, type FieldValues, type UseFormRegister } from "react-hook-form";
import { api } from "@/api/endpoints";
import { useToast } from "@/app/useToast";
import { Section } from "@/components/Section";
import type { Settings, SettingsPatch, SettingsSection } from "@/types/api";
import { SECTION_META, label } from "./settingsMeta";
import styles from "./SettingsPage.module.css";

/**
 * Build the settings patch from flat form values, preserving the legacy
 * semantics: numeric fields -> numbers, `allowed_extensions` -> string[],
 * everything else -> strings.
 */
function buildPatch(values: FieldValues, current: Settings): SettingsPatch {
  const patch: SettingsPatch = {};

  for (const [section] of SECTION_META) {
    const sectionData = current[section] as SettingsSection | undefined;
    if (!sectionData) continue;

    for (const [key, initial] of Object.entries(sectionData)) {
      if (Array.isArray(initial)) continue; // arrays handled separately
      const formKey = `${section}.${key}`;
      const raw = values[formKey];
      if (raw === undefined || raw === null) continue;

      let value: unknown = raw;
      if (typeof initial === "number") {
        const num = Number(raw);
        if (raw === "" || Number.isNaN(num)) continue; // skip invalid numbers
        value = num;
      } else if (key === "allowed_extensions") {
        value = String(raw)
          .split(/[\s,]+/)
          .filter(Boolean);
      }
      (patch[section] as Record<string, unknown>) ??= {};
      (patch[section] as Record<string, unknown>)[key] = value;
    }
  }

  const universe = String(values["default_universe"] ?? "")
    .trim()
    .split(/[\s,]+/)
    .filter(Boolean)
    .map((s) => s.toUpperCase());
  patch.default_universe = universe;

  return patch;
}

export default function SettingsPage() {
  const { toast } = useToast();
  const queryClient = useQueryClient();

  const settingsQuery = useQuery({ queryKey: ["settings"], queryFn: api.settings });
  const defaultsQuery = useQuery({
    queryKey: ["settings", "defaults"],
    queryFn: api.settingsDefaults,
  });

  const saveMutation = useMutation({
    mutationFn: (patch: SettingsPatch) => api.updateSettings(patch),
    onSuccess: () => {
      toast("Settings saved");
      void queryClient.invalidateQueries({ queryKey: ["settings"] });
    },
    onError: (e) => toast(e instanceof Error ? e.message : "Save failed"),
  });

  const resetMutation = useMutation({
    mutationFn: api.resetSettings,
    onSuccess: () => {
      toast("Reset to defaults");
      void queryClient.invalidateQueries({ queryKey: ["settings"] });
    },
    onError: (e) => toast(e instanceof Error ? e.message : "Reset failed"),
  });

  if (settingsQuery.isPending || defaultsQuery.isPending) {
    return (
      <div className="center">
        <span className="spinner" /> Loading settings…
      </div>
    );
  }

  if (settingsQuery.isError || defaultsQuery.isError || !settingsQuery.data || !defaultsQuery.data) {
    const err = (settingsQuery.error ?? defaultsQuery.error) as unknown;
    return <div className="center">{err instanceof Error ? err.message : "Failed to load settings"}</div>;
  }

  return (
    <SettingsForm
      current={settingsQuery.data}
      defaults={defaultsQuery.data}
      saving={saveMutation.isPending || resetMutation.isPending}
      onSave={(patch) => saveMutation.mutate(patch)}
      onReset={() => resetMutation.mutate()}
    />
  );
}

function SettingsForm({
  current,
  defaults,
  saving,
  onSave,
  onReset,
}: {
  current: Settings;
  defaults: Settings;
  saving: boolean;
  onSave: (patch: SettingsPatch) => void;
  onReset: () => void;
}) {
  const { register, handleSubmit } = useForm<FieldValues>();

  const submit = handleSubmit((values) => onSave(buildPatch(values, current)));

  return (
    <form onSubmit={submit}>
      <Section
        title="Settings"
        sub="Tune how the screener behaves. Changes apply immediately and are saved. Use Reset to restore factory defaults."
      />

      {SECTION_META.map(([section, title, sub]) => (
        <SettingsSectionCard
          key={section}
          section={section}
          title={title}
          sub={sub}
          current={current}
          defaults={defaults}
          register={register}
        />
      ))}

      <div className="card">
        <div style={{ fontWeight: 700, fontSize: 17, marginBottom: 2 }}>
          {label("default_universe")}
        </div>
        <div className="mini" style={{ marginBottom: 8 }}>
          Stocks scanned when the Scan symbol box is left empty. Separate with spaces or commas.
        </div>
        <textarea
          rows={4}
          defaultValue={current.default_universe.join(" ")}
          {...register("default_universe")}
        />
        <div className="mini" style={{ marginTop: 6 }}>
          Default: {defaults.default_universe.length} Nifty-50 stocks
        </div>
      </div>

      <div className="row">
        <button type="submit" className="btn" disabled={saving}>
          Save changes
        </button>
        <button
          type="button"
          className="btn secondary"
          disabled={saving}
          onClick={() => {
            if (window.confirm("Reset all settings to factory defaults?")) onReset();
          }}
        >
          Reset to default
        </button>
      </div>
      <div style={{ height: 14 }} />
    </form>
  );
}

function SettingsSectionCard({
  section,
  title,
  sub,
  current,
  defaults,
  register,
}: {
  section: string;
  title: string;
  sub: string;
  current: Settings;
  defaults: Settings;
  register: UseFormRegister<FieldValues>;
}) {
  const sectionData = (current[section] ?? {}) as SettingsSection;
  const defaultsData = (defaults[section] ?? {}) as SettingsSection;

  return (
    <div className="card">
      <div style={{ fontWeight: 700, fontSize: 17, marginBottom: 2 }}>{title}</div>
      <div className="mini" style={{ marginBottom: 10 }}>
        {sub}
      </div>

      {Object.entries(sectionData).map(([key, value]) => {
        if (Array.isArray(value)) return null; // arrays handled separately
        const isNumber = typeof value === "number";
        const formKey = `${section}.${key}`;
        return (
          <div className={styles.setrow} key={key}>
            <div className={styles.setlab}>
              {label(key)}
              <span className={styles.setdef}>default {String(defaultsData[key])}</span>
            </div>
            <input
              className={styles.setnum}
              type={isNumber ? "number" : "text"}
              step={isNumber ? "any" : undefined}
              defaultValue={String(value)}
              {...register(formKey)}
            />
          </div>
        );
      })}
    </div>
  );
}
