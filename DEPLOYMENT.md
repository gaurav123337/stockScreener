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

No environment secrets are required for the basic Yahoo Finance-backed preview. Render injects `PORT`; the container start command uses it automatically.

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

## Update Or Remove

- Pushes to the connected branch trigger a new deployment.
- Use **Manual Deploy > Deploy latest commit** in Render to retry a deployment.
- To stop public access, suspend or delete the service from the Render dashboard.
- Never commit generated files under `data/` or real broker credentials.
