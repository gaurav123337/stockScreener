import { useQuery } from "@tanstack/react-query";
import { api } from "@/api/endpoints";
import { Section } from "@/components/Section";
import { Card } from "@/components/ui/Card";
import { LoadingState } from "@/components/ui/Spinner";
import { ArrowLeft, BookOpen } from "lucide-react";
import { Link, useParams } from "react-router-dom";

export default function LearnDetailPage() {
  const { slug = "" } = useParams();

  const articleQuery = useQuery({
    queryKey: ["learn", slug],
    queryFn: () => api.learnDetail(slug),
    enabled: Boolean(slug),
  });

  if (articleQuery.isPending) return <LoadingState />;
  if (articleQuery.isError || !articleQuery.data) {
    return (
      <>
        <Link to="/learn" className="mb-3 inline-flex items-center gap-1 text-sm font-semibold text-brand">
          <ArrowLeft className="size-4" aria-hidden />
          Back to Learn
        </Link>
        <p className="py-6 text-center text-sm text-muted">This guide could not be loaded.</p>
      </>
    );
  }

  const article = articleQuery.data;
  const related = article.related_slugs ?? [];

  return (
    <>
      <Link to="/learn" className="mb-3 inline-flex items-center gap-1 text-sm font-semibold text-brand">
        <ArrowLeft className="size-4" aria-hidden />
        Back to Learn
      </Link>

      <Section title={article.title} sub={article.tagline} />

      <p className="mb-4 flex items-center gap-1.5 text-xs text-muted">
        <BookOpen className="size-3.5" aria-hidden />
        {article.reading_minutes} min read · {article.category}
      </p>

      <div className="space-y-3">
        {article.sections.map((section, index) => (
          <Card key={`${section.heading}-${index}`} className="p-5">
            <h2 className="text-[17px] font-bold text-ink">{section.heading}</h2>
            {section.body && (
              <div className="mt-2 space-y-2 text-sm leading-6 text-ink">
                {section.body.split("\n\n").map((paragraph, i) => (
                  <p key={i}>{paragraph}</p>
                ))}
              </div>
            )}
            {section.bullets.length > 0 && (
              <ul className="mt-3 grid gap-1.5">
                {section.bullets.map((bullet, i) => (
                  <li key={i} className="flex gap-2 text-sm leading-6 text-ink">
                    <span className="mt-2.5 size-1.5 shrink-0 rounded-full bg-brand" aria-hidden />
                    <span>{bullet}</span>
                  </li>
                ))}
              </ul>
            )}
          </Card>
        ))}
      </div>

      {related.length > 0 && (
        <Card className="mt-4 p-5">
          <h3 className="font-bold text-ink">Keep learning</h3>
          <div className="mt-2 flex flex-wrap gap-2">
            {related.map((rel) => (
              <Link
                key={rel}
                to={`/learn/${rel}`}
                className="inline-flex items-center rounded-full border border-border bg-surface-raised px-3 py-1.5 text-xs font-semibold text-brand hover:border-focus"
              >
                {rel.replace(/-/g, " ")}
              </Link>
            ))}
          </div>
        </Card>
      )}

      <p className="mt-4 text-xs text-muted">Educational content. Not investment advice.</p>
    </>
  );
}
