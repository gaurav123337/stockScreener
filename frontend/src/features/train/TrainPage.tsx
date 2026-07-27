import { useRef, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { api } from "@/api/endpoints";
import { useToast } from "@/app/useToast";
import { Section } from "@/components/Section";
import type { LearnResult } from "@/types/api";

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

      <div className="card">
        <div style={{ fontWeight: 700, fontSize: 17, marginBottom: 8 }}>Upload a file</div>
        <div className="mini" style={{ marginBottom: 8 }}>
          PDF, .md, .txt, or video transcript (.txt/.srt/.vtt). For a video, upload its
          subtitle/transcript file.
        </div>
        <input ref={fileRef} type="file" accept=".pdf,.md,.txt,.srt,.vtt" />
        <div style={{ height: 10 }} />
        <button className="btn" onClick={upload} disabled={fileMutation.isPending}>
          Upload & Learn
        </button>
      </div>

      <div className="card">
        <div style={{ fontWeight: 700, fontSize: 17, marginBottom: 8 }}>Add a URL</div>
        <div className="mini" style={{ marginBottom: 8 }}>
          Blog post / article / research note (public link).
        </div>
        <input
          type="text"
          placeholder="https://example.com/article"
          inputMode="url"
          value={url}
          onChange={(e) => setUrl(e.target.value)}
        />
        <div style={{ height: 10 }} />
        <button
          className="btn secondary"
          onClick={fetchUrl}
          disabled={urlMutation.isPending}
        >
          Fetch & Learn
        </button>
      </div>

      <div className="card">
        <div style={{ fontWeight: 700, fontSize: 17, marginBottom: 8 }}>Knowledge base</div>
        <div className="mini" style={{ marginBottom: 8 }}>
          What the screener has learned so far (rules it follows).
        </div>
        <button
          className="btn ghost"
          onClick={() => knowledgeMutation.mutate()}
          disabled={knowledgeMutation.isPending}
        >
          View knowledge base
        </button>
        <div style={{ marginTop: 10 }}>
          {knowledgeMutation.isPending && (
            <div className="center">
              <span className="spinner" />
            </div>
          )}
          {knowledge !== null && !knowledgeMutation.isPending && (
            <div
              className="card"
              style={{
                whiteSpace: "pre-wrap",
                fontSize: 12,
                maxHeight: 320,
                overflow: "auto",
              }}
            >
              {knowledge}
            </div>
          )}
        </div>
      </div>
    </>
  );
}
