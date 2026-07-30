import type { FeedbackCategory } from "@/types/api";

export const TITLE_MIN = 3;
export const TITLE_MAX = 120;
export const DETAILS_MIN = 10;
export const DETAILS_MAX = 5000;

export const CATEGORY_OPTIONS: ReadonlyArray<{ value: FeedbackCategory; label: string }> = [
  { value: "concern", label: "Concern" },
  { value: "bug", label: "Bug" },
  { value: "idea", label: "Idea" },
  { value: "other", label: "Other" },
];
