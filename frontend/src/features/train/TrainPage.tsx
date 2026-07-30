import { api } from "@/api/endpoints";
import { useToast } from "@/app/useToast";
import { Section } from "@/components/Section";
import { Button } from "@/components/ui/Button";
import { Card, CardTitle } from "@/components/ui/Card";
import { LoadingState } from "@/components/ui/Spinner";
import { controlClass, helpTextClass } from "@/components/ui/styles";
import type { LearnResult } from "@/types/api";
import { useMutation } from "@tanstack/react-query";
import { useRef, useState } from "react";

function learnMessage(result: LearnResult): string {
  if (result.ok === false) return result.error ?? "failed";
  const rules = result.rules_added ?? 0;
  return result.saved_as
    ? `Learned ${rules} rules from ${result.saved_as}`
    : `Learned ${rules} rules`;
}

export default function TrainPage() {
  const { toast } = useToast();
  const fileRef = useRef<HTMLInputElement>(null);
  const [url, setUrl] = useState("");
  const [knowledge, setKnowledge] = useState<string | null>(null);

  const fileMutation = useMutation({
    mutationFn: (file: File) => api.learnFile(file),
    onSuccess: (r) => toast(learnMessage(r)),
    onError: (e) => toast(e instanceof Error ? e.message : "Upload failed"),
    onSettled: () => {
      if (fileRef.current) fileRef.current.value = "";
    },
  });

  const urlMutation = useMutation({
    mutationFn: (u: string) => api.learnUrl(u),
    onSuccess: (r) => toast(learnMessage(r)),
    onError: (e) => toast(e instanceof Error ? e.message : "Fetch failed"),
  });

  const knowledgeMutation = useMutation({
    mutationFn: api.knowledge,
    onSuccess: (r) => setKnowledge(r.content || "Empty"),
    onError: (e) => toast(e instanceof Error ? e.message : "Failed to load"),
  });

  const upload = () => {
    const file = fileRef.current?.files?.[0];
    if (!file) {
      toast("Choose a file first");
      return;
    }
    toast(`Learning from ${file.name}…`);
    fileMutation.mutate(file);
  };

  const fetchUrl = () => {
    const u = url.trim();
    if (!u) {
      toast("Paste a URL");
      return;
    }
    toast("Fetching & learning…");
    urlMutation.mutate(u);
  };

  return (
    <>
      <Section
        title="Train"
        sub="Keep the screener updated — upload PDFs, notes/blogs, video transcripts, or paste a URL. It extracts market rules into its knowledge base."
      />

      <Card>
        <CardTitle className="mb-2">Upload a file</CardTitle>
        <p className={helpTextClass}>
          PDF, .md, .txt, or video transcript (.txt/.srt/.vtt). For a video, upload its
          subtitle/transcript file.
        </p>
        <input
          className={controlClass}
          ref={fileRef}
          type="file"
          accept=".pdf,.md,.txt,.srt,.vtt"
        />
        <Button className="mt-3" onClick={upload} disabled={fileMutation.isPending}>
          Upload & Learn
        </Button>
      </Card>

      <Card>
        <CardTitle className="mb-2">Add a URL</CardTitle>
        <p className={helpTextClass}>Blog post / article / research note (public link).</p>
        <input
          className={controlClass}
          type="text"
          placeholder="https://example.com/article"
          inputMode="url"
          value={url}
          onChange={(e) => setUrl(e.target.value)}
        />
        <Button
          className="mt-3"
          variant="secondary"
          onClick={fetchUrl}
          disabled={urlMutation.isPending}
        >
          Fetch & Learn
        </Button>
      </Card>

      <Card>
        <CardTitle className="mb-2">Knowledge base</CardTitle>
        <p className={helpTextClass}>What the screener has learned so far (rules it follows).</p>
        <Button
          className="mt-3"
          variant="ghost"
          onClick={() => knowledgeMutation.mutate()}
          disabled={knowledgeMutation.isPending}
        >
          View knowledge base
        </Button>
        <div className="mt-3">
          {knowledgeMutation.isPending && <LoadingState />}
          {knowledge !== null && !knowledgeMutation.isPending && (
            <pre className="max-h-80 overflow-auto whitespace-pre-wrap rounded-lg border border-border bg-canvas p-3 text-xs text-ink">
              {knowledge}
            </pre>
          )}
        </div>
      </Card>
    </>
  );
}
