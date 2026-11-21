# HG Lab: Stem-loop RT-qPCR Primer Designer

Automated primer design tool for Stem-loop RT-qPCR miRNA quantification.

## Requirements
- Node.js 20+
- Python 3.11+
- Internet connection (for miRBase API)
- NCBI BLAST+ (`blastn`, `blastdbcmd` on PATH) for the off-target check. The backend runs it with `BLAST_USAGE_REPORT=false` unless you set that variable yourself: BLAST+ otherwise reports every run to NCBI, which added about 1 s per call and hung 30–35 s on a slow network (NCBI documents this variable as the switch; the hits do not change).

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
