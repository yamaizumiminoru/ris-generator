# Deployment & Release Guide

## 1. Directory Tree for Repository
This is the recommended structure for your `ris-generator` repository:

```text
ris-generator/
├── src/
│   ├── config.py
│   ├── extraction.py
│   ├── gui.py
│   ├── main.py
│   ├── processor.py
│   └── worker.py
├── .gitignore
├── CHANGELOG.md
├── LICENSE
├── README.md
├── requirements.txt
├── RisGenerator.spec
└── SECURITY.md
```

## 2. SHA256 Checksum Generation
Run this command in PowerShell to generate the hash for your release artifact:

```powershell
certutil -hashfile dist/RisGenerator.exe SHA256 > SHA256SUMS.txt
```
*Clean up the output file to only contain the hash and filename if desired.*

**Current Build Hash (v1.0.0):**
`27460db634b344b619f63f617336509c3d7d521a5b75a4d382bc633fe9b0300db`

## 3. Deployment Checklist

- [ ] **Initialize Repo**: `git init`, `git add .`, `git commit -m "Initial commit"`
- [ ] **Create Repo on GitHub**: Name it `ris-generator`.
- [ ] **Push Code**: `git remote add origin ...`, `git push -u origin main`
- [ ] **Create Release v1.0.0**:
  - Go to "Releases" -> "Draft a new release".
  - Tag version: `v1.0.0`
  - Title: `v1.0.0 - Initial Release`
  - Description: Copy from `CHANGELOG.md`.
  - **Attach binaries**: Drag & drop `dist/RisGenerator.exe` and `SHA256SUMS.txt`.
  - Click "Publish release".
- [ ] **Update README Link**:
  - Once the "RIS Linker" plugin repo is created, update the `Related Projects` link in `README.md`.

## 4. Related Projects Placeholder
In `README.md`, the related project link is currently:
`[Zotero plugin "RIS Linker"](https://github.com/yamaizumiminoru/ris-linker)`

**Action**: Verify this URL is correct when you create the Zotero plugin repo.
