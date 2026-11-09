# Gym Buddy

A single-user Streamlit app for tracking workouts, exercise sets and weights, daily activity, and simple health trends. Workout and activity data are stored in Google Sheets.

The attached schedule is used as editable starter data. It specifies sets and reps/durations but no working weights; the app asks you to record weights before it can show a useful weight reference.

## Features

- Password-only login using a bcrypt hash (the original password is never saved by the app).
- Today's workout selected from the configured timezone, with short-session and full-plan views.
- Per-exercise set logging for actual reps/duration and optional weight.
- Weight reference from previous workouts. A small increase is suggested only after all target sets and reps are completed at the same weight for two consecutive logged sessions. Treat a suggestion as optional; keep the weight only when it feels comfortable and your form stays controlled.
- Daily entries for gym attendance (including days the gym is closed), morning walk/jog and gym duration, steps, calories, water, optional protein, weekly body weight, and optional monthly waist measurement.
- Weekly in-app summaries and optional body-measurement charts.
- Permanent workout and daily-health history organized into calendar-year tabs for year-by-year comparison.
- Editable plan. A shortened session displays exercises marked `is_core`.

This tracker is for personal record-keeping and is not medical advice, a diagnosis, or a replacement for your doctor's guidance.

## Local setup

Use Python 3.11 or newer. Open PowerShell in the project folder. If you already created `.venv`, use it—do not create a second environment:

```powershell
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

If you do not have a virtual environment yet, create one first:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

### 1. Create a Google spreadsheet

1. Create a new Google Sheet using the Google account you want to own your workout data.
2. Copy the spreadsheet ID from its URL. For a URL like `https://docs.google.com/spreadsheets/d/abc123/edit`, the ID is `abc123` (the part between `/d/` and `/edit`). You will put this in your app secrets.
3. Keep the spreadsheet private; the app's service account will be granted access in a later step.

You do not need to create tabs or column headers yourself. On its first successful connection, Gym Buddy creates `WorkoutPlan` plus year-specific activity tabs such as `WorkoutSets_2026` and `DailyHealth_2026`. It adds the starter workout schedule to `WorkoutPlan` if that tab is blank or has only its header row. Blank existing tabs are initialized with the required headers.

### 2. Create a Google service account

The service account is the app's identity when it accesses your spreadsheet. It is separate from your personal Google login.

1. In [Google Cloud Console](https://console.cloud.google.com/), create or select a Google Cloud project.
2. Open **APIs & Services → Library**, search for **Google Sheets API**, and enable it for that project.
3. Open **IAM & Admin → Service Accounts** and create a service account (for example, `gym-buddy-sheets`).
4. Open the new service account's **Keys** tab, choose **Add key → Create new key → JSON**, and download the key file.
5. Treat that downloaded JSON as a password: anyone with it may access spreadsheets shared with the service account. Do not commit it, email it, or put it in your project folder. If it is exposed, delete/revoke that key in Google Cloud and create a new one.
6. Open your Google Sheet's **Share** dialog. Add the service account's `client_email` (the address ending in `iam.gserviceaccount.com` from the JSON file), grant **Editor** access, and share.

The app uses the Google Sheets API. It does not need Google Drive API access for this setup.

### 3. Set your login password and local secrets

The app does **not** store the original password. The generator below prompts for it without echoing it and writes a bcrypt hash to the terminal. Bcrypt is a one-way password hash, not reversible encryption.

```powershell
python utils\generate_password_hash.py
```

Copy the complete `$2b$12$...` hash it prints. Do not copy or save the password itself in `.env`, the spreadsheet, or the source code.

For local use, create a Streamlit secrets file. The app already supports this format, and it avoids having to put the service-account private key in a one-line environment variable:

```powershell
New-Item -ItemType Directory -Force .streamlit
Copy-Item .streamlit\secrets.example.toml .streamlit\secrets.toml
notepad .streamlit\secrets.toml
```

Replace the example values in `.streamlit\secrets.toml`:

```toml
GYM_BUDDY_PASSWORD_HASH = "$2b$12$PASTE_THE_COMPLETE_BCRYPT_HASH_HERE"
GOOGLE_SHEETS_ID = "PASTE_THE_ID_FROM_THE_SHEET_URL"
APP_TIMEZONE = "Asia/Kolkata"
WEIGHT_UNIT = "kg"
WEIGHT_INCREASE_PERCENT = "2.5"

[gcp_service_account]
type = "service_account"
project_id = "your-google-cloud-project-id"
private_key_id = "paste-private_key_id-from-downloaded-json"
private_key = """-----BEGIN PRIVATE KEY-----
Paste the complete private_key value from the downloaded JSON here.
Keep the BEGIN and END lines; preserve the key's line breaks.
-----END PRIVATE KEY-----
"""
client_email = "paste-client_email-from-downloaded-json"
client_id = "paste-client_id-from-downloaded-json"
token_uri = "https://oauth2.googleapis.com/token"
```

Use the **matching values from the downloaded JSON key file** for `project_id`, `private_key_id`, `private_key`, `client_email`, and `client_id`. The `private_key` must be the full key, including its `BEGIN PRIVATE KEY` and `END PRIVATE KEY` lines. Keep the quotes around the bcrypt hash and spreadsheet ID. Do not share the completed secrets file or its contents.

The file `.streamlit\secrets.toml` is excluded by `.gitignore`; verify it does not appear in files you commit. The provided `.streamlit\secrets.example.toml` contains placeholders only and can be copied safely.

Alternatively, local configuration can be supplied through `.env`; copy `.env.example` to `.env` and set `GYM_BUDDY_PASSWORD_HASH`, `GOOGLE_SHEETS_ID`, and `GOOGLE_SERVICE_ACCOUNT_JSON` (the complete service-account JSON encoded as one line). Do not configure conflicting values in both `.env` and `secrets.toml`; environment variables take precedence over Streamlit secrets.

### 4. Start the app

With the project's virtual environment activated:

```powershell
streamlit run app.py
```

Enter the original password you chose at the login screen. Your password is checked against the bcrypt hash; it is not sent to Google Sheets. When you first open the app with valid Sheets credentials, the three data tabs are created automatically.

### Change your password

Run `python utils\generate_password_hash.py` again, then replace `GYM_BUDDY_PASSWORD_HASH` in `.streamlit\secrets.toml` (or `.env`) with the newly generated hash and restart Streamlit. The old password will stop working. If the original password is forgotten, the app cannot recover it from the bcrypt hash; choose a new one and generate a replacement hash.

### Troubleshooting Google Sheets connection

- **Spreadsheet not found / access denied:** confirm `GOOGLE_SHEETS_ID` is only the ID (not the whole URL) and that you shared the sheet with the exact service-account `client_email` as an Editor.
- **Invalid credentials:** check that you pasted the complete JSON key fields into `[gcp_service_account]`, especially the private key including its BEGIN/END lines. Revoke and replace the key if it was exposed.
- **API disabled:** check that Google Sheets API is enabled in the same Google Cloud project as the service account.
- **Unexpected worksheet headers:** do not rename, reorder, or edit the header row in the app-created tabs.
- After changing secrets, restart the Streamlit process so it reloads them.

`WEIGHT_UNIT` accepts `kg` or `lb`. The default timezone is `Asia/Kolkata`; change `APP_TIMEZONE` to a valid IANA timezone if needed. The weight increase percentage defaults to 2.5%, rounded up to a practical increment (0.5 kg or 2.5 lb).

## Streamlit Community Cloud deployment

1. Push the project to a private GitHub repository. Do not commit `.env` or the service-account JSON key.
2. Create a Streamlit Community Cloud app from the repository with `app.py` as the entry point.
3. In the app's **Settings → Secrets**, add:

```toml
GYM_BUDDY_PASSWORD_HASH = "$2b$12$..."
GOOGLE_SHEETS_ID = "your_spreadsheet_id"
APP_TIMEZONE = "Asia/Kolkata"
WEIGHT_UNIT = "kg"
WEIGHT_INCREASE_PERCENT = "2.5"

[gcp_service_account]
type = "service_account"
project_id = "your-project-id"
private_key_id = "your-private-key-id"
private_key = """-----BEGIN PRIVATE KEY-----
your-private-key
-----END PRIVATE KEY-----
"""
client_email = "your-service-account@your-project.iam.gserviceaccount.com"
client_id = "your-client-id"
token_uri = "https://oauth2.googleapis.com/token"
```

Use the same Google Cloud and spreadsheet setup described above, then replace every placeholder with your own values. Add the settings in **Streamlit Community Cloud → your app → Settings → Secrets**. Treat Streamlit secrets and the original private key as credentials. The app expects the service-account object under `[gcp_service_account]`.

## Data and privacy

The spreadsheet has these tabs:

- `WorkoutPlan`: editable weekly schedule and target sets/amounts.
- `WorkoutSets_YYYY`: one row per logged set, including date, exercise, actual amount, and weight. A new tab is created automatically for each calendar year.
- `DailyHealth_YYYY`: one row per date with gym attendance, activity duration, and optional health metrics. A new tab is created automatically for each calendar year. Existing yearly health tabs are upgraded with the attendance column while preserving existing rows.

Activity history is retained across years; the app does not automatically delete old workout or health records. The weekly report reads all annual tabs and includes a year-by-year summary and monthly training-time comparison. Keep a separate backup of your spreadsheet as you would for any important data.

## Tests

```powershell
python -m pytest
```

The tests cover rep-range parsing, weight-progression eligibility, and the retention cutoff. A live Sheets test requires a configured spreadsheet and service-account credentials.
