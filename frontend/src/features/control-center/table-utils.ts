export const tableClass =
  "w-full min-w-[720px] text-left text-sm [&_th]:border-b [&_th]:border-border [&_th]:px-3 [&_th]:py-2 [&_th]:text-xs [&_th]:font-semibold [&_th]:uppercase [&_th]:text-muted [&_td]:border-b [&_td]:border-border/70 [&_td]:px-3 [&_td]:py-3";

export function formatDate(value: string | null | undefined) {
  return value
    ? new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(
        new Date(value),
      )
    : "Never";
}
