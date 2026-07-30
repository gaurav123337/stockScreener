import { useEffect, useRef, useState } from "react";
import { api } from "@/api/endpoints";
import type { SearchResult } from "@/types/api";

export function useStockAutocomplete() {
  const [search, setSearch] = useState("");
  const [results, setResults] = useState<SearchResult[] | null>(null);
  const [isOpen, setIsOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const query = search.trim();
    if (query.length < 2) {
      setIsOpen(false);
      setResults(null);
      return;
    }

    const timeout = window.setTimeout(async () => {
      try {
        const response = await api.search(query);
        setResults(response.results ?? []);
        setIsOpen(true);
      } catch {
        // Search suggestions are optional; scanning remains available on failure.
      }
    }, 220);

    return () => window.clearTimeout(timeout);
  }, [search]);

  useEffect(() => {
    function closeOnOutsideClick(event: MouseEvent) {
      if (!containerRef.current?.contains(event.target as Node)) setIsOpen(false);
    }

    document.addEventListener("click", closeOnOutsideClick);
    return () => document.removeEventListener("click", closeOnOutsideClick);
  }, []);

  return { search, setSearch, results, isOpen, setIsOpen, containerRef };
}
