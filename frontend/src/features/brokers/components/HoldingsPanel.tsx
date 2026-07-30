import { Button } from "@/components/ui/Button";
import { Card, CardTitle } from "@/components/ui/Card";
import { LoadingState } from "@/components/ui/Spinner";

export function HoldingsPanel(props: {
  holdings: string | null;
  loading: boolean;
  onFetch: () => void;
}) {
  return (
    <Card>
      <CardTitle className="mb-2">My holdings / positions</CardTitle>
      <Button variant="secondary" onClick={props.onFetch} disabled={props.loading}>
        Fetch from connected broker
      </Button>
      <div className="mt-3">
        {props.loading && <LoadingState />}
        {props.holdings !== null && !props.loading && (
          <pre className="max-h-72 overflow-auto whitespace-pre-wrap rounded-lg border border-border bg-canvas p-3 text-xs text-ink">
            {props.holdings}
          </pre>
        )}
      </div>
    </Card>
  );
}
