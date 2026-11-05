# A2R Operations Console

Windows desktop app (Python + CustomTkinter) for receipt extraction, auto-printing and archiving.

## Required files in the repo root
- `collect.py` (main script)
- `app.ico`
- `pdftotext.exe` (Xpdf/Poppler)
- `SumatraPDF.exe` (optional, for silent 57x90 mm printing)

## Build locally
```
pip install -r requirements.txt
python -m PyInstaller --clean --noconsole --onefile --icon=app.ico --add-binary "pdftotext.exe;." --add-binary "SumatraPDF.exe;." --collect-all customtkinter --collect-all reportlab --collect-all arabic_reshaper --collect-all bidi --collect-all pystray --collect-all PIL --hidden-import pystray._win32 --name A2R_Console collect.py
```

## Build on GitHub
- Every push to `main` builds the exe: Actions -> latest run -> Artifacts -> `A2R_Console`.
- To publish a release: `git tag v4.30.0 && git push origin v4.30.0`.
