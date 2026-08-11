import { Section } from "@/components/Section";
import { Card, CardTitle } from "@/components/ui/Card";

const GUIDE_SECTIONS: ReadonlyArray<{ title: string; items: readonly string[] }> = [
  {
    title: "What each signal means",
    items: [
      "BUY — uptrend + momentum + reasonable valuation. Enter near the shown entry, target and stop-loss. Risk:Reward shown.",
      "SELL — downtrend / weakening momentum. Exit or avoid.",
      "HOLD — mixed signals. Wait for confirmation.",
      "Always use the stop-loss and risk only 1-2% of capital per trade.",
    ],
  },
  {
    title: "Scanning & filters",
    items: [
      "Use Scan → pick a pre-defined filter (e.g. momentum, oversold).",
      "Or type a custom filter like rsi < 35 and roe > 0.15.",
      "Fields: score price rsi pe peg roe debt_to_equity sma50 sma200 above_sma50 above_sma200 golden_cross near_52w_high near_52w_low.",
    ],
  },
  {
    title: "Keep it updated (Train)",
    items: [
      "Drop research PDFs, notes, or video transcripts in Train to add their rules to the knowledge base.",
      "Paste URLs of good blogs/articles to ingest them.",
      "The screener logs every call and scores its own Signal Score hit-rate at 30/90/365-day horizons. See Track Record for the published walk-forward results.",
    ],
  },
  {
    title: "What is the Signal Score?",
    items: [
      "The score is a rule-based blend of trend, momentum, volume and fundamentals — not a magic 'AI' prediction.",
      "Confidence measures how much those pillars agree and how strong the signal is. It is a transparency measure, not a probability of profit.",
      "Every claim sits on real evidence: open Track Record to see dated hit-rates vs the NIFTY50 benchmark.",
    ],
  },
  {
    title: "Broker APIs",
    items: [
      "Open Brokers → follow the steps for Zerodha Kite or Angel One SmartAPI.",
      "Connecting gives live LTP and pulls your holdings/positions.",
      "Zerodha tokens expire daily — re-login each morning.",
    ],
  },
  {
    title: "Install on mobile",
    items: [
      "On Android (Chrome) tap Install at the top, or menu → Add to Home screen.",
      "On iPhone (Safari) tap Share → Add to Home Screen.",
      "Make sure your phone is on the same network as this server, or host it online (HTTPS) for install anywhere.",
    ],
  },
];

export default function GuidePage() {
  return (
    <>
      <Section title="Guide" sub="How to get the most out of the platform." />

      {GUIDE_SECTIONS.map((section) => (
        <Card key={section.title}>
          <CardTitle>{section.title}</CardTitle>
          <ol className="mt-2 list-decimal space-y-2 pl-5 text-sm leading-6 text-muted">
            {section.items.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ol>
        </Card>
      ))}

      <p className="mt-4 text-center text-xs text-muted">
        Educational tool — not SEBI-registered investment advice.
      </p>
    </>
  );
}
