import { useQuery } from "@tanstack/react-query";
import { api } from "@/api/endpoints";
import { Section } from "@/components/Section";
import { Card } from "@/components/ui/Card";
import { controlClass } from "@/components/ui/styles";
import { LoadingState } from "@/components/ui/Spinner";
import { BookOpen, Search } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";

export default function LearnPage() {
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState("");

  const learnQuery = useQuery({
    queryKey: ["learn", query, category],
    queryFn: () => api.learnList(query.trim(), category || undefined),
    placeholderData: (prev) => prev,
  });

  const articles = learnQuery.data?.articles ?? [];
  const categories = [...new Set(articles.map((a) => a.category))];

  return (
    <>
      <Section
        title="Learn"
        sub="Plain-language guides to the concepts behind every screen, score and plan in stockScreener."
      />

      <div className="mb-4 grid gap-3 sm:grid-cols-[1fr_auto]">
        <label className="relative">
          <Search
            className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted"
            aria-hidden
          />
          <input
            className={controlClass + " pl-9"}
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Search guides, e.g. P/E ratio"
          />
        </label>
        {categories.length > 0 && (
          <select
            className={controlClass + " sm:w-44"}
            value={category}
            onChange={(event) => setCategory(event.target.value)}
          >
            <option value="">All topics</option>
            {categories.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
        )}
      </div>

      {learnQuery.isPending ? (
        <LoadingState />
      ) : articles.length === 0 ? (
        <p className="py-6 text-center text-sm text-muted">No guides match your search.</p>
      ) : (
        <div className="grid gap-3">
          {articles.map((article) => (
            <Card key={article.slug} className="p-5">
              <Link to={`/learn/${article.slug}`} className="group block">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="text-xs font-semibold uppercase tracking-wide text-brand">
                      {article.category}
                    </p>
                    <h2 className="mt-1 font-bold leading-snug text-ink group-hover:text-brand">
                      {article.title}
                    </h2>
                    <p className="mt-1 line-clamp-2 text-sm leading-6 text-muted">
                      {article.excerpt}
                    </p>
                    <p className="mt-2 flex items-center gap-1.5 text-xs text-muted">
                      <BookOpen className="size-3.5" aria-hidden />
                      {article.reading_minutes} min read
                    </p>
                  </div>
                </div>
              </Link>
            </Card>
          ))}
        </div>
      )}
    </>
  );
}
