import { PageHeader } from "./ui/PageHeader";

export function Section({ title, sub }: { title: string; sub: string }) {
  return <PageHeader title={title} description={sub} />;
}
