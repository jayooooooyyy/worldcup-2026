# Deployment Guide

Recommended first deployment target: Streamlit Community Cloud.

## Deploy Checklist

Before deploying:

1. Push this project to a GitHub repository.
2. Confirm these files are in the repository root:
   - `requirements.txt`
   - `.streamlit/config.toml`
   - `dashboard/app.py`
3. Do not commit secrets:
   - `.env` is ignored.
   - `.streamlit/secrets.toml` is ignored.
   - Use Streamlit Cloud app secrets for API keys.

## Streamlit Community Cloud

1. Go to Streamlit Community Cloud.
2. Click **Create app** or **Deploy now**.
3. Choose the GitHub repository.
4. Set **Main file path** to:

```text
dashboard/app.py
```

5. Leave Python version on the default unless Streamlit asks.
6. Deploy.

## Streamlit Secrets

The current dashboard can run without API-Football secrets because it reads committed CSV outputs and live Polymarket public endpoints.

For future API-Football refresh jobs, add this in Streamlit Cloud **Settings → Secrets**:

```toml
API_FOOTBALL_KEY = "your_api_football_key"
```

Do not paste secrets into source code.

## Data Used By The Dashboard

The deployed app reads committed local files:

- `data/processed/world_cup_2026_prediction_markets.csv`
- `data/processed/world_cup_2026_predictions_final.csv`
- `data/processed/group_simulation_2026.csv`
- `data/processed/model_prediction_accuracy_summary.csv`
- `data/actuals/world_cup_2026_actual_results.csv`
- `data/external/polymarket/*.csv`
- `data/reports/diagnostics/calibrated_v3_summary.csv`
- `data/reports/model_version_summary.csv`

Live Polymarket odds are fetched on demand from public endpoints inside the app.

## Local Commands

Run locally:

```bash
streamlit run dashboard/app.py
```

Refresh API-Football data locally:

```bash
API_FOOTBALL_KEY=your_key .venv/bin/python scripts/update_api_football_data.py --fixture-limit 2
```

Fetch historical World Cup statistics for corner-model training:

```bash
API_FOOTBALL_KEY=your_key .venv/bin/python scripts/update_api_football_data.py --season 2022 --completed-only
API_FOOTBALL_KEY=your_key .venv/bin/python scripts/update_api_football_data.py --season 2018 --completed-only
API_FOOTBALL_KEY=your_key .venv/bin/python scripts/update_api_football_data.py --season 2014 --completed-only
API_FOOTBALL_KEY=your_key .venv/bin/python scripts/update_api_football_data.py --season 2010 --completed-only
```

## Other Platforms

Render, Railway, and Hugging Face Spaces can also run the app.

Start command:

```bash
streamlit run dashboard/app.py --server.headless true --server.port $PORT
```

For platforms that do not set `$PORT`, use:

```bash
streamlit run dashboard/app.py --server.headless true --server.port 8501
```
