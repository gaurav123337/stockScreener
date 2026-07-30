import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/api/endpoints";
import { useToast } from "@/app/useToast";
import { LoadingState } from "@/components/ui/Spinner";
import type { SettingsPatch } from "@/types/api";
import { SettingsForm } from "./components/SettingsForm";

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
    return <LoadingState>Loading settings…</LoadingState>;
  }

  if (
    settingsQuery.isError ||
    defaultsQuery.isError ||
    !settingsQuery.data ||
    !defaultsQuery.data
  ) {
    const err = (settingsQuery.error ?? defaultsQuery.error) as unknown;
    return (
      <div
        className="rounded-panel border border-rose-500/40 bg-rose-500/10 p-4 text-center text-sm text-danger"
        role="alert"
      >
        {err instanceof Error ? err.message : "Failed to load settings"}
      </div>
    );
  }

  return (
    <SettingsForm
      key={settingsQuery.dataUpdatedAt}
      current={settingsQuery.data}
      defaults={defaultsQuery.data}
      saving={saveMutation.isPending || resetMutation.isPending}
      onSave={(patch) => saveMutation.mutate(patch)}
      onReset={() => resetMutation.mutate()}
    />
  );
}
