# Golf Mental-Performance Dashboard

Interactive Streamlit dashboard for the Cameron Institute mental-performance interview presentation.

The app is separate from the Jupyter analysis notebooks and loads the Excel workbook from:

`data/Golfer Resilience Data Set.xlsx`

## Local Launch

From this folder:

```bash
pip install -r requirements.txt
streamlit run app.py
```

Open:

`http://localhost:8501`

The app opens to Team Overview with `Tournament + Qualifying` selected by default.

## Live Interview Fallback

If internet access fails during the interview, run locally:

```bash
./run_local.sh
```

On Windows:

```bat
run_local.bat
```

Then open `http://localhost:8501`.

Static fallback screenshots are stored in:

`dashboard_screenshots/`

## GitHub Deployment

1. Create a new GitHub repository.
2. Upload the full `golf_dashboard/` folder contents.
3. Confirm these files exist in the repository root:
   - `app.py`
   - `data_processing.py`
   - `requirements.txt`
   - `data/Golfer Resilience Data Set.xlsx`
4. Commit and push to GitHub.

## Streamlit Community Cloud Deployment

1. Go to `https://share.streamlit.io` or `https://streamlit.io/cloud`.
2. Choose **New app**.
3. Select the GitHub repository.
4. Set the main file path to:

   `app.py`

5. Deploy.

The final URL will look like:

`https://<project-name>.streamlit.app`

## Adding the Dashboard Link to PowerPoint

In PowerPoint:

1. Select the text or button, for example: `Explore the Athlete Dashboard`.
2. Choose **Insert -> Link -> Existing File or Web Page**.
3. Paste the deployed Streamlit URL.
4. During the interview, click the link to open the dashboard.

## Data and Interpretation Notes

- Underlying event/opportunity counts are unavailable.
- Team benchmarks are unweighted averages of available athlete rates.
- Statistical significance cannot be evaluated from the supplied data.
- Tournament + Qualifying cannot be decomposed into qualifying-only performance without underlying counts.
- Metric denominator details should be confirmed.
- These transition metrics are descriptive behavioral indicators, not direct measures of psychological state.

