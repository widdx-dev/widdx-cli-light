---
name: file-reader
description: Read any file type correctly — PDF, DOCX, XLSX, CSV, JSON, images, code, logs, archives. First check size, then choose the right tool. Never dump binary to stdout.
icon: 📄
---

# File Reader — Smart File Handling for WIDDX

When you need to read a file, **never** blindly `cat` or `read` everything.
This skill tells you the right first move for each type.

---

## Protocol for Every File

1. **Check the extension** — that's your dispatch key
2. **Check the size** before reading — use `wc -c` via bash
3. **Read just enough** to answer — don't load a 100MB file into context
4. **If it's binary, NEVER use `read`** — it prints garbage

---

## Dispatch Table by Extension

| Extension | Tool | Command / Method |
|-----------|------|------------------|
| `.txt` `.md` `.log` `.py` `.js` `.html` `.css` `.json` `.cfg` `.toml` `.yaml` `.yml` `.xml` `.csv` `.tsv` `.sh` `.bat` `.ps1` | `read` | `read(file_path, offset=0, limit=100)` |
| `.pdf` | `bash` (Python) | `python3 -c "import PyPDF2; r=PyPDF2.PdfReader('FILE'); print(f'{len(r.pages)} pages'); [print(p.extract_text()[:500]) for p in r.pages[:2]]"` |
| `.docx` | `bash` (Python) | `python3 -c "from docx import Document; d=Document('FILE'); [print(p.text[:300]) for p in d.paragraphs[:10]]"` |
| `.xlsx` `.xlsm` | `bash` (Python) | `python3 -c "import pandas as pd; x=pd.ExcelFile('FILE'); print(x.sheet_names); df=pd.read_excel('FILE',nrows=5); print(df)"` |
| `.json` | `read` or `bash` | Small: `read`. Large: `python3 -c "import json; d=json.load(open('FILE')); print(type(d), list(d.keys())[:10] if isinstance(d,dict) else len(d) if isinstance(d,list) else 'scalar')"` |
| `.png` `.jpg` `.gif` `.webp` `.svg` | `bash` (Python) | `python3 -c "from PIL import Image; i=Image.open('FILE'); print(i.size,i.mode,i.format)"` |
| `.zip` | `bash` | `python3 -c "import zipfile; z=zipfile.ZipFile('FILE'); z.printdir()"` |
| `.tar` `.tar.gz` `.tgz` | `bash` | `python3 -c "import tarfile; t=tarfile.open('FILE'); [print(m.name) for m in t.getmembers()[:20]]"` |
| `.mp3` `.wav` `.mp4` `.avi` | `bash` | `python3 -c "import os; s=os.stat('FILE'); print(f'{s.st_size} bytes, media file — cannot read as text')"` |
| `.db` `.sqlite` `.sqlite3` | `bash` | `python3 -c "import sqlite3; c=sqlite3.connect('FILE'); tables=[t[0] for t in c.execute(\"SELECT name FROM sqlite_master WHERE type='table'\")]; print(tables); [print(t,c.execute(f'SELECT COUNT(*) FROM [{t}]').fetchone()[0]) for t in tables]"` |

---

## Step-by-Step Examples

### 1. Text Files (`.txt` `.md` `.py` `.js` etc.)

```
Step 1: Check size
  bash: wc -c FILEPATH
Step 2: Read based on size
  < 2000 lines → read(FILEPATH)
  > 2000 lines → read(FILEPATH, offset=0, limit=200)
  Need specific info → grep first, then read around the match
```

### 2. PDF Files

```
Step 1: Check page count + extract first pages
  bash: python3 -c "
import PyPDF2
r = PyPDF2.PdfReader('FILEPATH')
print(f'Pages: {len(r.pages)}')
for i, page in enumerate(r.pages[:3]):
    text = page.extract_text()
    if text.strip():
        print(f'--- Page {i+1} ---')
        print(text[:300])
"
Step 2: If no text extracted (scan/image PDF) → tell user it's a scanned PDF
Step 3: For specific info, loop through pages with grep-like search
```

### 3. DOCX Files

```
Step 1: Extract text
  bash: python3 -c "
from docx import Document
d = Document('FILEPATH')
for i, p in enumerate(d.paragraphs[:20]):
    if p.text.strip():
        print(f'[{i}] {p.text[:200]}')
"
Step 2: Check tables
  python3 -c "
from docx import Document
d = Document('FILEPATH')
print(f'Tables: {len(d.tables)}')
for i, t in enumerate(d.tables):
    print(f'Table {i}: {len(t.rows)} rows x {len(t.columns)} cols')
"
```

### 4. Excel / CSV

```
Step 1: Quick overview (Excel)
  bash: python3 -c "
import pandas as pd
x = pd.ExcelFile('FILEPATH')
print('Sheets:', x.sheet_names)
for s in x.sheet_names:
    df = pd.read_excel('FILEPATH', sheet_name=s, nrows=3)
    print(f'\n--- {s} ---')
    print(df.head())
"

Step 2: For CSV, use read with limit first
  read(FILEPATH, limit=20)

Step 3: For full analysis  
  bash: python3 -c "
import pandas as pd
df = pd.read_csv('FILEPATH')
print(df.describe())
print(df.dtypes)
"
```

### 5. JSON Files

```
Step 1: Check structure
  bash: python3 -c "
import json
with open('FILEPATH') as f:
    d = json.load(f)
if isinstance(d, dict):
    print(f'Object with {len(d)} keys: {list(d.keys())[:15]}')
elif isinstance(d, list):
    print(f'Array with {len(d)} items')
    if d: print(f'First item keys: {list(d[0].keys()) if isinstance(d[0],dict) else type(d[0]).__name__}')
else:
    print(type(d).__name__, str(d)[:100])
"

Step 2: For specific keys, extract just what's needed
  bash: python3 -c "
import json
with open('FILEPATH') as f:
    d = json.load(f)
print(json.dumps(d.get('KEY_NAME', d), indent=2)[:500])
"
```

### 6. Archives (ZIP/TAR)

```
Step 1: List contents (NEVER auto-extract)
  bash: python3 -c "
import zipfile
z = zipfile.ZipFile('FILEPATH')
for info in z.infolist():
    print(f'{info.file_size:>10}  {info.filename}')
print(f'Total: {len(z.infolist())} files')
"

Step 2: Read one file from archive
  bash: python3 -c "
import zipfile, io
z = zipfile.ZipFile('FILEPATH')
data = z.read('path/inside/archive.txt')
print(data.decode('utf-8', errors='replace')[:500])
"
```

### 7. SQLite Databases

```
Step 1: List tables with row counts
  bash: python3 -c "
import sqlite3
c = sqlite3.connect('FILEPATH')
tables = [t[0] for t in c.execute(\"SELECT name FROM sqlite_master WHERE type='table'\").fetchall()]
for t in tables:
    count = c.execute(f'SELECT COUNT(*) FROM [{t}]').fetchone()[0]
    print(f'{t}: {count} rows')
"

Step 2: Preview a table
  python3 -c "
import sqlite3
c = sqlite3.connect('FILEPATH')
rows = c.execute('SELECT * FROM TABLENAME LIMIT 5').fetchall()
cols = [d[0] for d in c.description]
print(cols)
for r in rows: print(r)
"
```

---

## Large File Protocol

When a file is > 10,000 lines or > 1MB:

1. **Always stat first** — `bash: wc -c FILEPATH`
2. **Sample, don't slurp** — read first 50 lines + last 50 lines
3. **Search, don't scan** — use `grep` to find what you need
4. **Use Python for structured files** — `nrows` for pandas, pages for PDF
5. **Never load the whole thing** unless the user explicitly asks

---

## Binary File Warning

If you accidentally `read` a binary file and see garbage (`��NULSOH�`), STOP.
That's binary. Switch to the appropriate method above.

---

## Available WIDDX Tools for Reading

| Tool | Use For |
|------|---------|
| `read(file, offset, limit)` | Text files, code, logs, CSV |
| `grep(pattern, path)` | Search inside files |
| `glob(pattern)` | Find files by name |
| `bash(command)` | Python one-liners for PDF/DOCX/XLSX/ZIP |
| `web_fetch(url)` | Read remote files/web pages |

---

## Quick Reference Card

```
.txt .md .py .js .html .css .json .yaml → read(FILE)
.pdf                                      → bash: PyPDF2
.docx                                     → bash: python-docx
.xlsx .xlsm .csv                          → bash: pandas
.zip .tar .gz                             → bash: zipfile/tarfile (list first!)
.png .jpg .gif                            → bash: PIL.Image (dimensions only)
.db .sqlite                               → bash: sqlite3
.mp3 .mp4 .avi                            → tell user it's media
```
