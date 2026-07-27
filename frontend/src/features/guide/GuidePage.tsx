import { Section } from "@/components/Section";

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
      "The screener logs every call and scores its own hit-rate after 30 days (see data/predictions.csv or CLI python main.py verify).",
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
        <div className="card" key={section.title}>
          <div style={{ fontWeight: 700, fontSize: 17, marginBottom: 6 }}>{section.title}</div>
          <ol style={{ paddingLeft: 20 }} className="mini">
            {section.items.map((item) => (
              <li key={item} style={{ margin: "8px 0" }}>
                {item}
              </li>
            ))}
          </ol>
        </div>
      ))}

      <div className="mini center" style={{ marginTop: 14 }}>
        Educational tool — not SEBI-registered investment advice.
      </div>
    </>
  );
}
