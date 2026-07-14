# SPEC — Phase 1: AI Chatbot Giải Thích Kết Quả (Stem-loop RT-qPCR)

> Tài liệu thiết kế kỹ thuật cho Phase 1. Mục tiêu: chatbot đọc kho bài báo khoa học + kết quả HRM (data số), trả lời câu hỏi người dùng **có trích dẫn nguồn**, chạy self-host $0 trên máy 16GB RAM không GPU.

---
- Đây là tài liệu nguồn sự thật duy nhất. Mọi quyết định kỹ thuật phải tuân theo spec này.
- Khi nhận task mới: đọc lại section liên quan trước khi viết bất kỳ dòng code nào.
- Không tự ý thêm tính năng, thay đổi layout, hoặc dùng thư viện ngoài danh sách cho phép.
- Trước mỗi `git commit`: chạy security check (kiểm tra hardcoded secrets, injection risk).
- **Ngôn ngữ UI:** All UI text MUST be in English — labels, tooltips, errors, warnings, placeholders, buttons. No Vietnamese in the UI layer.
- All user-facing strings: English only.
- Mỗi constant phải có comment nguồn trích dẫn — không để số "magic" không có nguồn.
- Trước mỗi `git commit`: chạy Superpower security check (xem Section 2b).
- Sau mỗi thay đổi UI có ý nghĩa: chạy Playwright E2E test liên quan 

## 0. Nguyên tắc xuyên suốt

**Thuật toán đo — LLM chỉ giải thích.** LLM không bao giờ tự tạo số liệu (Tm, ΔG), không tự đẻ primer, không phán kết quả HRM từ ảnh. Mọi con số đến từ code Python; LLM chỉ diễn giải và trích dẫn.

**Grounded — có nguồn hoặc không nói.** Câu trả lời phải dựa trên (a) đoạn bài báo truy xuất được, hoặc (b) bảng số HRM đã tính. Không đủ căn cứ thì trả lời "không đủ dữ liệu để kết luận".

**Self-host, data không rời máy.** LLM + embedding + DB đều chạy local. Data người dùng không gửi cho bên thứ ba.

**Lớp abstraction cho LLM.** Mọi lời gọi LLM đi qua một hàm duy nhất `ask_llm()`. Nâng cấp model / đổi sang GPU / API sau này chỉ sửa 1 chỗ.

---

## 1. Kiến trúc tổng thể

```
┌─────────────────────────────────────────────────────────────┐
│                     FRONTEND (React + Vite)                  │
│  Chat UI  │  Upload/hiển thị HRM  │  Panel trích dẫn nguồn   │
└───────────────────────────┬─────────────────────────────────┘
                            │  HTTP (JSON) / REST
┌───────────────────────────┴─────────────────────────────────┐
│                       BACKEND (Flask)                        │
│                                                              │
│  ┌────────────┐  ┌────────────┐  ┌─────────────────────┐    │
│  │ Ingest bài │  │ Xử lý HRM  │  │   RAG Brain         │    │
│  │ báo        │  │ (data số)  │  │  retrieve→prompt→LLM│    │
│  └─────┬──────┘  └─────┬──────┘  └──────────┬──────────┘    │
│        │               │                    │               │
│  ┌─────┴───────────────┴────────────────────┴──────────┐   │
│  │  SQLite (metadata+abstract)  │  ChromaDB (vector)     │   │
│  └───────────────────────────────────────────────────────┘  │
│                                                              │
│  ask_llm()  ──►  Ollama (Llama 3.2 3B / Qwen2.5 3B, CPU)     │
│  embed()    ──►  sentence-transformers (S-PubMedBert)        │
└──────────────────────────────────────────────────────────────┘
```

Bốn khối chức năng: **Ingest bài báo**, **Xử lý HRM**, **RAG Brain**, **Web UI**. Hai kho lưu trữ: **SQLite** (dữ liệu có cấu trúc + text gốc) và **ChromaDB** (vector để tìm kiếm ngữ nghĩa).

---

## 2. Tech stack (chốt)

| Thành phần | Lựa chọn | Ghi chú |
|---|---|---|
| Frontend | React + Vite | Đã có sẵn |
| Backend | Flask (Python 3.10+) | Đã có sẵn |
| LLM runtime | **Ollama** | Cài 1 lệnh, chạy CPU, có REST API local |
| LLM model | **Llama 3.2 3B** hoặc **Qwen2.5 3B** (Q4) | ~2–3GB RAM, trả lời vài giây. Nâng 7B sau qua abstraction |
| Embedding | **sentence-transformers** + `S-PubMedBert` | Model y sinh → tìm bài đúng hơn. Nhẹ hơn: `all-MiniLM-L6-v2` |
| Vector DB | **ChromaDB** | Embedded, không cần server riêng |
| DB có cấu trúc | **SQLite** | Có sẵn trong Python, 1 file |
| HRM processing | numpy/scipy + script sẵn có | normalizer.py, derivative.py, difference.py |
| Nguồn bài báo | PubMed (E-utilities) + open-access | Metadata + abstract |

RAM ước tính lúc chạy: LLM 3B (~3GB) + embedding (~0.5GB) + Flask/OS → gọn trong 16GB.

---

## 3. Khối 1 — Ingest bài báo

### 3.1 Nguồn
Tìm bài liên quan tới: quy trình (protocol), panel, thiết kế primer, phản ứng stem-loop RT-qPCR, HRM. Nguồn: PubMed (E-utilities API, miễn phí), bổ sung preprint/open-access.

### 3.2 Quy trình ingest
1. Query theo từ khoá → lấy danh sách PMID.
2. Lấy metadata + abstract cho từng PMID.
3. Lưu vào SQLite (bảng `papers`).
4. Tách abstract thành đoạn (chunk ~200–400 từ, overlap ~50 từ).
5. Tạo embedding cho từng chunk → lưu ChromaDB, kèm `paper_id` để truy ngược.

### 3.3 Bản quyền
Chỉ lưu **metadata + abstract + link**. Full-text chỉ lưu với bài **open-access**. Không lưu PDF tạp chí đóng.

### 3.4 Schema SQLite

```sql
CREATE TABLE papers (
    id            INTEGER PRIMARY KEY,
    pmid          TEXT UNIQUE,
    title         TEXT,
    authors       TEXT,          -- JSON list
    journal       TEXT,
    year          INTEGER,
    abstract      TEXT,
    url           TEXT,
    is_open_access INTEGER DEFAULT 0,
    full_text     TEXT,          -- chỉ khi open-access
    ingested_at   TEXT
);

CREATE TABLE chunks (
    id         INTEGER PRIMARY KEY,
    paper_id   INTEGER REFERENCES papers(id),
    chunk_text TEXT,
    chunk_index INTEGER,
    vector_id  TEXT               -- id trong ChromaDB
);
```

---

## 4. Khối 2 — Xử lý HRM (data số)

### 4.1 Input
Người dùng upload **data số**, không phải ảnh. Định dạng đề xuất: CSV/TSV với cột `temperature` và một hoặc nhiều cột mẫu (`sample_1`, `sample_2`, ..., kèm chứng dương/âm nếu có).

```
temperature, positive_ctrl, negative_ctrl, sample_1, sample_2
65.0,        0.98,          0.05,          0.97,     0.10
65.5,        0.95,          0.05,          0.94,     0.11
...
```

### 4.2 Pipeline tính đặc trưng (Python, dùng script sẵn có)
1. **Normalize** (normalizer.py — bilinear normalization) → F_norm ∈ [0,1].
2. **Derivative** (derivative.py) → đường −dF/dT.
3. **Difference** (difference.py) → đường sai khác so với chứng dương.
4. **Trích đặc trưng** cho mỗi mẫu:
   - Tm (đỉnh của −dF/dT)
   - số peak
   - chiều cao peak, độ rộng nửa chiều cao (FWHM)
   - độ lệch Tm so với chứng dương
   - phân loại sơ bộ: khớp / lệch / nhiễu / nghi ngờ

### 4.3 Output: **bảng số** (không phải ảnh)
Đây là thứ đưa vào LLM để diễn giải:

```json
{
  "sample_1": {
    "Tm": 79.4, "num_peaks": 1, "peak_height": 0.42,
    "fwhm": 1.8, "delta_Tm_vs_pos": -0.2, "flag": "match"
  },
  "sample_2": {
    "Tm": 76.1, "num_peaks": 2, "peak_height": 0.18,
    "fwhm": 3.5, "delta_Tm_vs_pos": -3.5, "flag": "suspect"
  }
}
```

Ảnh đường cong (nếu có) **chỉ để hiển thị trên UI**, không dùng làm nguồn phân tích.

### 4.4 Kiểm chứng thuật toán
Dùng skill `hrm-algorithm-validator` (đã có trong project) để unit-test normalize/derivative/difference với synthetic data trước khi tin kết quả.

---

## 5. Khối 3 — RAG Brain

### 5.1 Luồng trả lời một câu hỏi
1. Nhận câu hỏi + (tuỳ chọn) bảng số HRM của phiên làm việc.
2. `embed(câu hỏi)` → truy xuất top-k chunk gần nhất từ ChromaDB (k ≈ 4–6).
3. Lấy metadata bài báo tương ứng từ SQLite (để trích dẫn).
4. Dựng prompt: system rule + đoạn bài báo (kèm nhãn nguồn) + bảng số HRM + câu hỏi.
5. `ask_llm(prompt)` → câu trả lời.
6. Trả về frontend: nội dung + danh sách nguồn đã dùng.

### 5.2 Prompt system (bản rút gọn)

```
Bạn là trợ lý phân tích phản ứng stem-loop RT-qPCR/HRM.
QUY TẮC:
- Chỉ trả lời dựa trên ĐOẠN BÀI BÁO và BẢNG SỐ HRM được cung cấp.
- Mọi con số phải lấy từ BẢNG SỐ, KHÔNG tự tính, KHÔNG tự đoán.
- KHÔNG đề xuất/tạo sequence primer ở Phase này.
- Mỗi ý dựa trên bài báo phải ghi nguồn dạng [1], [2].
- Không đủ căn cứ → nói rõ "không đủ dữ liệu để kết luận".
- Trả lời bằng tiếng Việt, ngắn gọn, chính xác.
```

### 5.3 Guardrails
- **Chống bịa số:** con số trong câu trả lời phải đối chiếu được với bảng HRM; nếu LLM trả số lạ → gắn cờ / lọc.
- **Bắt buộc trích dẫn:** câu trả lời dựa trên bài báo mà không có `[n]` → cảnh báo.
- **Chặn phạm vi Phase 2:** nếu người dùng hỏi "thiết kế primer giúp tôi" → trả lời rằng chức năng gợi ý tối ưu thuộc Phase 2, Phase 1 chỉ giải thích.

### 5.4 Lớp abstraction

```python
def ask_llm(prompt: str, **opts) -> str:
    # Phase 1: gọi Ollama local
    # Sau này: đổi sang GPU / API chỉ ở đây
    ...

def embed(texts: list[str]) -> list[list[float]]:
    # sentence-transformers, model config 1 chỗ
    ...
```

---

## 6. API Flask (đề xuất endpoint)

| Method | Endpoint | Chức năng |
|---|---|---|
| POST | `/api/ingest` | Nhận từ khoá → tìm & lưu bài báo vào DB |
| GET  | `/api/papers` | Liệt kê bài đã lưu (phân trang) |
| POST | `/api/hrm/analyze` | Nhận CSV HRM → trả bảng số + dữ liệu vẽ đường cong |
| POST | `/api/chat` | Nhận câu hỏi (+ hrm session) → trả câu trả lời + nguồn |
| GET  | `/api/health` | Kiểm tra Ollama/DB sống |

Ví dụ response `/api/chat`:

```json
{
  "answer": "Mẫu sample_2 có 2 peak và Tm lệch −3.5°C so với chứng dương, gợi ý sản phẩm không đặc hiệu hoặc primer-dimer [1].",
  "sources": [
    {"n": 1, "title": "...", "authors": "...", "year": 2021, "url": "https://pubmed..."}
  ],
  "used_hrm": true
}
```

---

## 7. Cấu trúc thư mục đề xuất

```
project/
├── frontend/                 # React + Vite
│   └── src/components/
│       ├── ChatPanel.jsx
│       ├── HRMUpload.jsx
│       ├── HRMChart.jsx      # chỉ hiển thị
│       └── SourcesPanel.jsx
├── backend/                  # Flask
│   ├── app.py                # routes
│   ├── llm.py                # ask_llm(), embed()  ← abstraction
│   ├── ingest/
│   │   ├── pubmed.py         # gọi E-utilities
│   │   └── indexer.py        # chunk + embed + lưu Chroma
│   ├── hrm/
│   │   ├── normalizer.py     # (sẵn có)
│   │   ├── derivative.py     # (sẵn có)
│   │   ├── difference.py     # (sẵn có)
│   │   └── features.py       # trích Tm, peak, flag
│   ├── rag/
│   │   ├── retriever.py
│   │   └── prompt.py
│   ├── db/
│   │   ├── schema.sql
│   │   └── store.py          # SQLite + Chroma
│   └── requirements.txt
└── data/
    ├── papers.db             # SQLite
    └── chroma/               # vector store
```

---

## 8. Lộ trình triển khai (milestone)

**M1 — Hạ tầng (nền).** Cài Ollama + kéo model 3B; dựng `llm.py` (`ask_llm`, `embed`); tạo SQLite + ChromaDB rỗng; `/api/health` chạy.

**M2 — Ingest bài báo.** `pubmed.py` + `indexer.py`; `/api/ingest` và `/api/papers`; kiểm tra tìm & lưu được bài thật.

**M3 — Xử lý HRM.** `features.py` trên nền script sẵn có; `/api/hrm/analyze` trả bảng số; validate bằng skill hrm-algorithm-validator.

**M4 — RAG Brain.** `retriever.py` + `prompt.py`; `/api/chat` nối retrieve→LLM→nguồn; bật guardrails.

**M5 — Frontend.** ChatPanel + HRMUpload + HRMChart + SourcesPanel; nối API.

**M6 — Kiểm thử & tinh chỉnh.** Test end-to-end với bộ câu hỏi mẫu; so 3B vs 7B; kiểm tra trích dẫn đúng, không bịa số.

---

## 9. Rủi ro & hướng xử lý

| Rủi ro | Hướng xử lý |
|---|---|
| LLM 3B trả lời yếu / lệch | Grounding tốt + prompt chặt; thử Qwen2.5 3B vs Llama 3.2 3B; nâng 7B qua abstraction |
| CPU inference chậm | Dùng model Q4 nhỏ; giới hạn độ dài context; stream token cho cảm giác nhanh hơn |
| Retrieval sai bài | Dùng embedding y sinh (S-PubMedBert); tăng/giảm k; thêm lọc theo năm/từ khoá |
| LLM vẫn bịa số | Đối chiếu số với bảng HRM sau sinh; gắn cờ; hiển thị nguồn để người dùng kiểm |
| Bản quyền full-text | Chỉ metadata+abstract; full-text open-access; luôn kèm link gốc |
| Data HRM định dạng lạ | Chuẩn hoá 1 format CSV; validate cột đầu vào; báo lỗi rõ ràng |

---

## 10. Ngoài phạm vi Phase 1 (để dành Phase 2)

- Gợi ý tối ưu phản ứng / đề xuất primer.
- Lớp kiểm chứng nhiệt động học (Primer3, tính Tm/ΔG/dimer/hairpin) xác nhận đề xuất của LLM.
- Fine-tune model theo domain.

Phase 2 chỉ bắt đầu sau khi Phase 1 chạy ổn định và đáng tin.
