# crossreactivity — ma trận phản ứng chéo cấp assay

R(i, j) là mức tín hiệu mà assay thiết kế cho miRNA i (bộ mồi #1) nhận được từ miRNA j, so với tín hiệu của chính đích i.

R = 2^−ΔCq_assay = p_RT × p_PCR. ΔCq lấy từ mô hình assay của webtool (`backend/algorithm/specificity_check/assay_model.py`), **chưa hiệu chỉnh bằng wet-lab**. Các quyết định và giới hạn xem ở [`docs/DECISIONS_crossreactivity.md`](../docs/DECISIONS_crossreactivity.md).

## Chạy lại (từ thư mục gốc repo)

```bash
pip install -r backend/requirements.txt -r crossreactivity/requirements.txt
python -m crossreactivity.design_all      # mồi #1 cho mọi hsa miRNA (~5 phút, chạy tiếp được nếu bị ngắt)
python -m crossreactivity.build_matrix    # ma trận (~1 phút, 14 tiến trình)
python -m crossreactivity.plots           # heatmap + histogram
python -m crossreactivity.validate        # so với số liệu công bố (validation/crossreactivity_*.csv)
python -m pytest crossreactivity/tests -q
```

- **Cấu hình** nằm ở `config.json`: phiên bản và đường dẫn miRBase, loài, ngưỡng các mức, điều kiện tính ΔG.
- **Bộ nhớ đệm** ở `outputs/crossreactivity_cache/` (không commit); xóa thư mục này để tính lại từ đầu. Bộ đệm gắn với `ALGORITHM_VERSION`: sau khi đổi thuật toán, `design_all` thiết kế lại các miRNA cũ, còn `build_matrix` từ chối chạy cho tới khi thiết kế cùng phiên bản và không dùng lại block cũ.

## Đầu ra (`outputs/`)

| File | Nội dung |
|---|---|
| `crossreactivity_long.parquet` / `.csv` | Các cặp có R > 0 (mức HIGH / MEDIUM / LOW); cặp không có trong file là NONE (R < 0,1 %) |
| `crossreactivity_metadata.json` | Phiên bản tool, commit, config, ngày chạy, phiên bản miRBase và sha256, số cặp theo mức, kết quả kiểm tra đường chéo |
| `crossreactivity_row_stats.csv` | Theo từng assay: số cặp mỗi mức, R(i,i), R lớn nhất ngoài đường chéo |
| `crossreactivity_failed_designs.csv` | miRNA không thiết kế được, kèm lý do |
| `crossreactivity_top30_offdiagonal.csv` | 30 cặp R cao nhất giữa các phân tử khác nhau |
| `figures/heatmap_<họ>.{png,svg}`, `figures/r_histogram.{png,svg}` | Hình |

## API Python

```python
from crossreactivity.api import CrossReactivity, aggregate_expression

xr = CrossReactivity.load("outputs/crossreactivity_long.parquet")
xr.get_risk("hsa-let-7a-5p", "hsa-let-7d-5p")      # R, level, p_RT, p_PCR, …
xr.submatrix(["hsa-let-7a-5p", "hsa-let-7d-5p"])   # DataFrame N×N: hàng = assay, cột = miRNA được đo
groups = xr.assay_resolvable_groups(mirnas)        # {miRNA: đơn vị}, đối xứng hóa bằng max, ngưỡng 10 %
xr.group_report(groups)                            # liên kết yếu nhất trong mỗi đơn vị (phát hiện nối chuỗi)
features = aggregate_expression(rpm, groups)       # mẫu × đơn vị (RPM cộng dồn)
```

Hàm `load_matrix`, `get_risk`, `submatrix`, `assay_resolvable_groups` cũng có dạng hàm thường. Ví dụ chạy được: `python -m crossreactivity.example`.

**Tên miRNA phải theo miRBase 22.1.** Dữ liệu TCGA dùng mã MIMAT, nên cần ánh xạ sang tên trước khi gọi `aggregate_expression`.
