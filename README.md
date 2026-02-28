# ASTERIX Decoder — Build Guide

This document explains how to produce a standalone executable from the project,
either locally on your own machine or automatically via GitHub Actions.

---

## Project structure

```
project_root/
  main.py
  requirements.txt
  pyinstaller/
    linux.spec        ← spec file for Linux builds
    windows.spec      ← spec file for Windows builds
  .github/
    workflows/
      build_release.yml   ← GitHub Actions workflow
  ui/                 ← frontend static files
  connections/
  database/
  user_actions/
```

---

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