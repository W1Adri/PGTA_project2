# ASTERIX Decoder — Build Guide

ASTERIX Decoder is a desktop tool that ingests raw ASTERIX surveillance files, decodes CAT021/CAT048 messages, and exposes them through an interactive table and map for analysis and export.
ASTERIX (All Purpose Structured Eurocontrol Surveillance Information Exchange) is the EUROCONTROL standard format used to exchange air traffic surveillance data between sensors, processing systems, and ATM applications.


## Project structure

```
project_root/
  ASTERIX_notebook.ipynb
  main.py
  README.md
  requirements.txt
  asterix_decoder/
    decoder_service.py
    optimization.py
    data_items/
      data_item.py
      error_exceptions.py
      length_type.py
      CAT021/
      CAT048/
    data_tables/
      csv_table.py
      uap_tables.py
    database/
      asterix_pandas.py
      filters.py
    helpers/
      compute_target_lat_lon.py
  connections/
    api.py
    websocket_handler.py
  user_actions/
    user_actions_manager.py
  ui/
    index.html
    js/
    styles/
  raw_data/
  output/
  pyinstaller/
    linux.spec
    windows.spec
```

---

## Deep dive: asterix_decoder

The `asterix_decoder` package is the decoding core. It receives raw ASTERIX bytes and produces a normalized pandas DataFrame used by the rest of the application.

### 1) Decoding orchestration (`decoder_service.py`)

This module contains the end-to-end pipeline:

1. Split binary stream into ASTERIX messages.
2. Parse each message FSPEC to determine active FRNs.
3. Build and cache FRN-to-decoder instances using UAP tables.
4. Decode item payloads into flat key-value fields.
5. Add derived fields (for example target geolocation from polar coordinates, and corrected altitude values).
6. Build the final output schema depending on categories present (CAT021, CAT048, or mixed) and return a DataFrame ready for filtering and rendering.

It also supports progress callbacks so decoding stages can be streamed to the frontend in real time. This exact pipeline is explained more detailed in the `ASTERIX_notebook.ipynb`, read it in order to undestand deeply how the .ast is decoded.

### 2) Data item system (`data_items/`)

This folder defines how each ASTERIX item is decoded:

- `data_item.py` provides the abstract `DataItem` contract (`get_item_id()` and `decode()`), common length parsing logic, and a fallback `ItemXXX` decoder for unknown or unimplemented items.
- `length_type.py` and `error_exceptions.py` support parsing semantics (fixed, variable, compound, repetitive) and controlled decode errors.
- `CAT021/` and `CAT048/` contain concrete decoders per item (for example I021/010, I048/020, etc.).

At runtime, `decoder_service.py` dynamically discovers these classes and maps each `(category, item_id)` to the corresponding implementation.

### 3) ASTERIX metadata tables (`data_tables/`)

This folder describes decoding and output schema:

- `uap_tables.py` defines FRN order and item metadata for CAT021 and CAT048 (which item appears in each FRN position).
- `csv_table.py` defines output column sets for CAT021-only, CAT048-only, and combined datasets.

These tables are used to construct stable output columns even when uploaded files differ in content.

### 4) In-memory data layer (`database/`)

This is the runtime data engine after decoding:

- `asterix_pandas.py` stores the session DataFrame with thread safety and exposes query operations used by API/WS layers:
  - metadata retrieval,
  - temporary filter application,
  - paginated table windows,
  - time-centered map windows,
  - CSV export bytes.
- `filters.py` contains filtering rules and normalization logic (category, target identification, flight level range, time range, on-ground, pure-white behavior, etc.).

Important architectural point: this store is the single source of truth shared across API and WebSocket servers.

### 5) Domain helper utilities (`helpers/`)

`compute_target_lat_lon.py` contains geometric/domain calculations used during decoding (for example converting radar polar information into target latitude/longitude).

### 6) Performance helpers (`optimization.py`)

This module groups decoding performance utilities used by the decoding pipeline to keep large-file processing responsive.

---

## Rest of the project structure (high level)

- `main.py`: application bootstrap. Starts FastAPI and WebSocket services in background threads, then opens the pywebview desktop window.
- `connections/`: transport layer implementations.
- `user_actions/`: WebSocket action router that maps frontend actions to store operations.
- `ui/`: frontend app (HTML shell, JavaScript modules, and styles). Kept modular by feature (upload, table, map, filters, socket client).
- `raw_data/`: sample ASTERIX binary files for manual testing.
- `output/`: generated decoded CSV output artifacts.
- `pyinstaller/`: packaging specifications for Linux and Windows executables.

---

## Communication model: API vs WebSocket

The app uses both HTTP API and WebSocket, with different responsibilities.

### API (FastAPI in `connections/api.py`)

Used for request/response operations and binary transfer:

- `POST /upload`: receives the ASTERIX file, triggers decoding, loads the shared in-memory store, and returns metadata immediately.
- `GET /download/csv`: returns CSV bytes from the current in-memory session.
- `GET /health`: service liveness and record count.
- `POST /table_data`: legacy/auxiliary paginated endpoint (the current table flow is primarily windowed WebSocket).
- Static frontend serving: mounts `ui/` at `/`.

Why API here:

- File upload and binary payloads fit naturally in HTTP multipart.
- CSV export is a classic streaming download.
- Stateless checks (health) are simpler over HTTP.

### WebSocket (server in `connections/websocket_handler.py`)

Used for low-latency, event-driven and high-frequency interactions:

- Progress push from backend during decoding (`decode_progress`).
- Action-based requests from frontend, dispatched by `user_actions/user_actions_manager.py`:
  - `apply_filters`
  - `get_metadata`
  - `clear_data`
  - `get_table_window`
  - `get_map_window`
  - `get_all` (debug/limited bulk)

Why WebSocket here:

- Table and map need frequent small window requests while scrolling/playing time.
- Server-to-client progress updates during decode are asynchronous pushes.
- Single persistent channel avoids repeated HTTP connection overhead for interactive UI behavior.

### End-to-end flow summary

1. Frontend uploads file through API (`POST /upload`).
2. Decoder processes bytes and stores DataFrame in shared `AsterixPandas`.
3. Decode progress is broadcast over WebSocket.
4. Frontend asks windows and filtered views over WebSocket (`get_table_window`, `get_map_window`, `apply_filters`).
5. Export is done over API (`GET /download/csv`).



# Build Guide

This document explains how to produce a standalone executable from the project,
either locally on your own machine or automatically via GitHub Actions.

## Option A — Build locally on your machine

Use this when you want a quick build on your own machine without involving
GitHub. The output runs only on the OS you build it on.

### Prerequisites

Make sure you are on your working branch (not necessarily `main` or `release`),
and that your virtual environment is active.

```bash
# Activate the virtual environment
source .venv/bin/activate          # Linux
.venv\Scripts\Activate.ps1         # Windows (PowerShell)
```

Install all dependencies including the build tools:

```bash
pip install -r requirements.txt
```

### Build on Linux

```bash
pyinstaller pyinstaller/linux.spec
```

The binary is produced at:

```
dist/asterix_decoder
```

Make it executable and run it:

```bash
chmod +x dist/asterix_decoder
./dist/asterix_decoder
```

### Build on Windows

Run from PowerShell or Command Prompt:

```powershell
pyinstaller pyinstaller/windows.spec
```

The executable is produced at:

```
dist\asterix_decoder.exe
```

Double-click it to run, or launch from the terminal:

```powershell
.\dist\asterix_decoder.exe
```

### Notes on local builds

- The spec files use `SPEC` to resolve paths relative to the project root,
  so always run `pyinstaller` from the project root directory, not from
  inside `pyinstaller/`.
- Build artefacts (`build/` and `dist/`) are local only. They are not
  committed to the repository.
- A local build only works on the OS where it was compiled. If you build
  on Linux you cannot run that binary on Windows, and vice versa.

---

## Option B — Automated build via GitHub Actions (recommended for releases)

Use this when you want to produce both a Linux binary and a Windows `.exe`
at the same time without needing access to a Windows machine, and publish
them as a permanent GitHub Release.

### How it works

Pushing to the `release` branch triggers the workflow
`.github/workflows/build_release.yml`, which:

1. Spins up a Linux runner and a Windows runner in parallel.
2. Installs all dependencies from `requirements.txt` on each.
3. Runs the corresponding `.spec` file on each platform.
4. Renames each binary with the platform name and current date/time.
5. Creates a permanent GitHub Release and attaches both binaries.

### Step-by-step

**1. Finish your work on your feature branch**

```bash
git add .
git commit -m "your message"
git push origin your-branch
```

**2. Merge your changes into `release`**

If the `release` branch does not exist yet, create it once:

```bash
git checkout -b release
git push origin release
```

On subsequent releases, bring it up to date with your branch:

```bash
git checkout release
git merge your-branch        # or git merge main if you merged there first
```

**3. Push to `release` to trigger the build**

```bash
git push origin release
```

The push is the trigger. The workflow starts automatically.

**4. Monitor the build**

Go to your repository on GitHub and click the **Actions** tab. You will see
a run called **Build Release Executables**. It contains three jobs:

```
prepare  →  build-linux  ─┐
                           ├─→  release
            build-windows ─┘
```

`build-linux` and `build-windows` run in parallel. The `release` job waits
for both to succeed before creating the GitHub Release. Total time is
typically 5–10 minutes.

If a job fails, click on it to read the logs. The **Verify installs** step
will tell you immediately if any required Python package is missing.

**5. Download the release**

Once the workflow finishes, go to:

```
https://github.com/YOUR-USERNAME/YOUR-REPO/releases
```

The latest release will be at the top, tagged `release-YYYY-MM-DD_HH-MM`
and named `ASTERIX Decoder — YYYY-MM-DD_HH-MM`. Under **Assets** you will
find:

```
asterix_decoder_linux_YYYY-MM-DD_HH-MM        ← Linux binary
asterix_decoder_windows_YYYY-MM-DD_HH-MM.exe  ← Windows executable
```

Both files are permanent and publicly downloadable (or privately, if the
repository is private).

---

## Comparison

| | Option A — Local build | Option B — GitHub Actions |
|---|---|---|
| Speed | Fast (no CI queue) | 5–10 min |
| Platforms | Current OS only | Linux + Windows simultaneously |
| Requires Windows or Linux machine | Yes | No, not even python just git commands |
| Output location | `dist/` on your machine | GitHub Releases page (permanent) |
| Sharable link | No | Yes |
| Triggered by | Running `pyinstaller` manually | Pushing to `release` branch |

---