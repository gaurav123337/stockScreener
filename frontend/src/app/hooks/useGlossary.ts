import { useQuery } from "@tanstack/react-query";
import { api } from "@/api/endpoints";

/** Plain-language glossary terms (cached for a day — copy changes rarely). */
export function useGlossary() {
  const query = useQuery({ queryKey: ["glossary"], queryFn: api.glossary, staleTime: 86_400_000 });
  return query.data?.terms ?? {};
}
