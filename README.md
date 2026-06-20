# HG Lab: Stem-loop RT-qPCR Primer Designer

Automated primer design tool for Stem-loop RT-qPCR miRNA quantification.

## Requirements
- Node.js 20+
- Python 3.11+
- Internet connection (for miRBase API)

## Running (open 2 terminals)

### Terminal 1 — Backend
```bash
cd backend
pip install -r requirements.txt
python app.py          # → http://localhost:5000
```

### Terminal 2 — Frontend
```bash
cd frontend
npm install
npm run dev            # → http://localhost:5173
```

## Quick check
1. Open http://localhost:5173 → tab title "HG Lab | Primer Designer"
2. Click the **Designer** tab
3. Enter `hsa-miR-21-5p` → press Tab → sequence auto-fills
4. Select **TaqMan** or **SYBR Green** → observe info box change

## Contact
https://hglab.hcmus.edu.vn
