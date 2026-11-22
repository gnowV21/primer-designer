# HG Lab: Stem-loop RT-qPCR Primer Designer

Automated primer design tool for Stem-loop RT-qPCR miRNA quantification.

## Requirements
- Node.js 20+
- Python 3.11+
- Internet connection only for miRNA names missing from the local miRBase 22.1 database (online lookups are labelled "release unknown")
- NCBI BLAST+ (`blastn`, `blastdbcmd` on PATH) for the off-target check. The backend runs it with `BLAST_USAGE_REPORT=false` unless you set that variable yourself: BLAST+ otherwise reports every run to NCBI, which added about 1 s per call and hung 30–35 s on a slow network (NCBI documents this variable as the switch; the hits do not change).

## Running (open 2 terminals)

### Terminal 1 — Backend
```bash
cd backend
pip install -r requirements.txt
python -m scripts.bootstrap_blast_db   # once: BLAST DB + db/mirbase.db from the pinned miRBase 22.1 file
python app.py          # → http://localhost:5000   (FLASK_DEBUG=1 for the debugger, PORT to change the port)
```

The BLAST DB and `db/mirbase.db` are not in git. Both are built from the committed
`backend/data/mirbase_22.1/mature.fa.gz` (sha256 in `SHA256`, the file the overhang and
family indexes come from); the build scripts refuse any other file and download only
with `--download`. miRBase CURRENT is 23.1 — do not build 4.0.0 from it.

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

## Deploy lên Vercel

Một container duy nhất (`Dockerfile.vercel`): gunicorn chạy Flask và phục vụ luôn
`frontend/dist` cùng origin (frontend gọi `/api` tương đối). BLAST DB và `db/mirbase.db`
được dựng **lúc build image** từ file miRBase 22.1 đã ghim, nên container khởi động không
tải hay dựng gì, và kết quả thiết kế trùng bản đóng băng 4.0.0
(`benchmark/deploy_equivalence.json`).

### Trên dashboard Vercel
1. **Add New → Project → Import** repo `primer-designer` từ GitHub.
2. **Framework Preset: Container** (Vercel nhận `Dockerfile.vercel` ở gốc repo; gốc có
   `package.json` của Playwright nên file phải mang tên `.vercel`). Không cần Build/Output
   command.
3. **Production Branch: `master`** (Settings → Git).
4. **Environment Variables** (Production + Preview):

   | Biến | Giá trị | Vì sao |
   |---|---|---|
   | `PORT` | `8080` | cổng app nghe (Vercel mặc định 80) |
   | `BLAST_USAGE_REPORT` | `false` | tắt báo cáo sử dụng của BLAST+ (mỗi lần gọi +1 s, có lúc treo 30–35 s) |
   | `BLAST_CLASSIFY_PROCESSES` | `2` | số tiến trình phân loại hit BLAST (RAM ≤ 2 GB) |
   | `BLAST_CACHE_PATH` | `/tmp/blast_cache.sqlite` | filesystem chỉ ghi được ở `/tmp` |

   Image đã đặt sẵn các giá trị này, cùng `VISUALIZE_CACHE_PATH=/tmp/visualize_cache.sqlite`
   và `PROXY_FIX_X_FOR=1` (lấy IP client từ `X-Forwarded-For` của proxy Vercel cho rate limit).
   Tùy chọn: `CORS_ORIGINS` (danh sách origin, phân cách bằng dấu phẩy) nếu một frontend
   ở origin khác gọi API.
5. **Deploy**, rồi mở `https://<project>.vercel.app/api/health` → `{"status": "ok", "version": "4.0.0"}`.

### Chạy image trên máy
```bash
docker build -f Dockerfile.vercel -t primer-designer .
docker run --rm -p 8080:8080 -e PORT=8080 primer-designer           # → http://localhost:8080
# giới hạn giống Vercel Hobby:
docker run --rm --cpus=1 --memory=2g -p 8080:8080 -e PORT=8080 primer-designer
# e2e vào container:
E2E_BASE_URL=http://localhost:8080 npx playwright test
# đo + đối chiếu với bản local (ghi benchmark/deploy_*.json):
python backend/scripts/deploy_check.py reference --out benchmark/logs/deploy_reference_local.json
python backend/scripts/deploy_check.py measure --image primer-designer --ref benchmark/logs/deploy_reference_local.json
```
Chạy không Docker (máy Linux có BLAST+): `Procfile` (bootstrap rồi gunicorn, `PORT` mặc định 5000).

### Hạn chế đã biết
- **Cold start:** instance tắt sau 5 phút không có traffic; request đầu sau đó phải chờ
  container khởi động (đo trên máy với `--cpus=1 --memory=2g`: 1,2–3,1 s tới `/api/health`;
  thời gian kéo image của Vercel không tính), và lần thiết kế đầu tiên của instance còn
  khởi động pool phân loại BLAST.
- **Thiết kế chậm hơn máy dev:** ở 1 CPU, thiết kế cache rỗng mất 15–24 s (máy dev nhiều
  nhân: ~5 s); frontend chờ tối đa 60 s. RAM đỉnh đo được 1,1–1,2 GB / 2 GB
  (`benchmark/deploy_timing_vercel.json`).
- **SIGTERM khi đang thiết kế:** gunicorn cho request đang chạy 25 s để xong; một thiết kế
  dài hơn thế lúc instance bị tắt sẽ bị cắt (người dùng bấm chạy lại).
- **Cache mất khi instance tắt:** cache BLAST và visualize nằm ở `/tmp`; thiết kế đầu tiên
  của mỗi miRNA trên một instance mới luôn chạy BLAST đầy đủ (kết quả không đổi, chỉ chậm hơn).
- **Rate limit đếm theo instance:** bộ đếm của flask-limiter ở bộ nhớ (`memory://`); Vercel
  có thể chạy nhiều instance, mỗi instance một bộ đếm riêng. Vì vậy gunicorn chạy **1 worker**
  (4 luồng).
- **Container Runtime của Vercel đang Beta:** nếu Vercel từ chối image, cùng
  `Dockerfile.vercel` chạy được trên Render / Railway / Fly.io (đặt cùng biến môi trường;
  các nơi đó tự gán `PORT`).
- Lịch sử thiết kế (`/history`) lưu trong IndexedDB của trình duyệt, không ở server.

## Contact
https://hglab.hcmus.edu.vn
