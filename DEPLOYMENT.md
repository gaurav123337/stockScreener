# Free Preview Deployment

## Recommended Environment: Render Free

This repository is configured as one Render web service. The container builds the React PWA, installs the Python dependencies, and serves the UI and API from FastAPI on the same HTTPS origin.

Render Free is suitable for a disposable early-testing preview:

- 750 free instance-hours per workspace each month
- automatic HTTPS and a public `onrender.com` URL
- direct deployment from the GitHub repository
- spins down after 15 minutes without inbound traffic
- usually takes up to about one minute to handle the first request after sleeping

### Data Persistence Warning

Render Free has an ephemeral filesystem. This app currently stores accounts, preferences, its token-signing key, predictions, learned files, and broker settings on local disk. That state can be lost whenever the service sleeps, restarts, or redeploys.

Treat this deployment as a disposable preview. Tell testers not to enter real broker credentials or rely on saved accounts/data. Durable testing requires replacing local SQLite/file persistence with an external managed database and object storage, or moving to a paid service with a persistent disk.

## Deploy From GitHub

1. Push this branch to `https://github.com/gaurav123337/stockScreener`.
2. Sign in at [Render](https://dashboard.render.com/) using GitHub.
3. Select **New > Blueprint**.
4. Connect the `stockScreener` repository.
5. Render detects `render.yaml`. Review the `stockscreener-preview` Free web service and select **Deploy Blueprint**.
6. Wait for the Docker build and health check to complete.
7. Open the assigned `https://stockscreener-preview-....onrender.com` URL.

No secrets are required for market-data access. Feedback email uses the Resend HTTPS API because Render Free blocks outbound SMTP ports 25, 465, and 587. The Blueprint prompts for:

- `RESEND_API_KEY`: an API key created in the Resend dashboard.
- `SCREENER_FEEDBACK_EMAIL_FROM`: a verified Resend sender, such as `Stock Screener <feedback@your-domain.example>`.
- `SCREENER_PRODUCT_OWNER_EMAIL`: the email address of the account that should receive Product Owner access. This is prompted as a secret/unmanaged value so it is not committed to Git.
- `SCREENER_PRODUCT_OWNER_INITIAL_PASSWORD`: a strong 12-128 character password used only if the configured Product Owner account does not exist yet. Keep it in Render's secret environment settings, never in Git.

Verify the sender domain in Resend before deploying, then enter both values in Render. The recipient remains `garudagaura@gmail.com` in `render.yaml`. If email configuration is missing or delivery fails, feedback is still persisted and available in the Product Owner control center; inspect Render logs for `email notification failed` and the Resend error response.

Render injects `PORT`; the container start command uses it automatically.

## Create the first Product Owner profile

Product Owner is an elevated role and cannot be selected during public registration. For a new Render deployment, use the deployment-owned bootstrap flow:

1. In Render's **Environment** settings, set `SCREENER_PRODUCT_OWNER_EMAIL` to the Product Owner's email.
2. Set `SCREENER_PRODUCT_OWNER_INITIAL_PASSWORD` to a unique password between 12 and 128 characters.
3. Deploy or restart the service. If the account does not exist, startup creates it as an email-verified `product_owner`. Sign in with those credentials and open `/control-center`.

The bootstrap is idempotent: later restarts find the same account and do not reset its password. Keep both values in Render because the free service's ephemeral filesystem can lose its SQLite database during a redeploy.

For an account that was already registered, do not set the initial-password variable. Verify the account first, then configure its email and restart. Locally, verification links are written to `data/auth_email_outbox.jsonl` because auth-email delivery is currently a development capture adapter.

Local direct bootstrap example:

```powershell
$env:SCREENER_PRODUCT_OWNER_EMAIL = "owner@example.com"
$env:SCREENER_PRODUCT_OWNER_INITIAL_PASSWORD = "use-a-unique-long-password"
python api.py
```

If startup reports `Configured product-owner account must have a verified email`, verify the pre-existing account or use a different email for deployment-owned creation. If it reports that the account was not found, either register and verify it or supply the initial password. Existing unverified accounts are never auto-promoted, preventing someone from pre-registering a known administrator email and gaining elevated access.

## Validate The Deployment

Open these URLs after deployment:

- `https://YOUR-SERVICE.onrender.com/api/health` should return `{"status":"ok","version":"0.4.0"}`.
- `https://YOUR-SERVICE.onrender.com/` should show the React app.
- Register a disposable test account, sign in, and request a recommendation.
- Let the service sit idle for at least 15 minutes, then confirm the expected cold-start delay.

## Local Container Check

```powershell
docker build -t stockscreener-preview .
docker run --rm -p 8000:8000 -e PORT=8000 stockscreener-preview
```

Then open `http://localhost:8000` and `http://localhost:8000/api/health`.

## Alternatives Considered

| Provider            | Free preview fit      | Main constraint                                                                                |
| ------------------- | --------------------- | ---------------------------------------------------------------------------------------------- |
| Render              | Recommended           | Sleeps after 15 minutes; local files are ephemeral                                             |
| Koyeb               | Viable alternative    | One free instance; scales to zero after 1 hour; no volume support on Free                      |
| PythonAnywhere      | Poor fit for this app | Free accounts restrict outbound internet, which conflicts with Yahoo Finance requests          |
| Hugging Face Spaces | Possible with Docker  | Better suited to public ML demos; persistent storage is not included in the basic free runtime |

Provider limits change. Recheck the official free-tier documentation before a wider release.

## Optional Indian Market Rollout

The Indian Market workspace is disabled by default and does not replace Yahoo
Finance. Configure these Render variables only after confirming the provider's
current official authentication and terms:

- `SCREENER_INDIAN_API_ENABLED=false` initially, then `true` for the preview.
- `SCREENER_INDIAN_API_BASE_URL` and `SCREENER_INDIAN_API_API_KEY` as secrets.
- `SCREENER_INDIAN_API_AUTH_HEADER` (default `X-Api-Key`).
- `SCREENER_INDIAN_API_AUTH_SCHEME` (empty by default; use `Bearer` only if the
  provider requires it).

Run the non-CI smoke check from the deployed application environment:

```powershell
python scripts/smoke_indian_api.py --stock RELIANCE
```

The command does not print response payloads or credentials. Product Owners can
inspect sanitized counters and latency at `/api/indian-market/status`. Keep
`SCREENER_MARKET_DATA_PROVIDER=yahoo` during Phase 4; the Indian API routes are
an explicitly separate research workspace until compatibility is approved.

## Update Or Remove

- Pushes to the connected branch trigger a new deployment.
- Use **Manual Deploy > Deploy latest commit** in Render to retry a deployment.
- To stop public access, suspend or delete the service from the Render dashboard.
- Never commit generated files under `data/` or real broker credentials.
