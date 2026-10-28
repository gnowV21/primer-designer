# SPEC — Week 2: Specificity Axis Correction & Scientific Reproducibility

> **Đối tượng đọc:** Claude Code (agent implement trực tiếp trên repo `primer-designer`).
> **Nguyên tắc:** mọi mục dưới đây là *chỉ thị thi hành*, không phải gợi ý. Nếu một chỉ thị mâu thuẫn
> với code hiện tại, code hiện tại sai — sửa code, đừng sửa spec. Nếu một chỉ thị mâu thuẫn với
> **§0.3 Bất biến**, DỪNG và báo lại, không tự quyết.
>
> **Ngôn ngữ:** phần diễn giải bằng tiếng Việt; **mọi identifier, key JSON, docstring, comment,
> commit message, và chuỗi hiển thị UI phải viết bằng tiếng Anh.**

---

## 0. Khung chung

### 0.1 Vấn đề cốt lõi mà SPEC này giải quyết

Tool đang gom nhóm miRNA theo **seed (vị trí 2–8 tính từ 5′)** rồi dùng nhóm đó làm cảnh báo
cross-reactivity cho primer. Seed là **trục nhắm mRNA sinh học**, không phải trục bám của primer.
Trong stem-loop RT-qPCR (Chen 2005), đặc hiệu được quyết định bởi hai trục hoàn toàn khác:

| Trục | Primer | Vùng quyết định trên miRNA | Cơ chế |
|---|---|---|---|
| **RT axis** | stem-loop RT primer | **6 nt cuối 3′** của mature miRNA | RT primer bắt cặp qua overhang; nếu không bám → không có cDNA |
| **FWD axis** | forward qPCR primer | **~12–18 nt đầu 5′** của mature miRNA | Forward primer mồi trên cDNA; nếu không phân biệt → co-amplification |

Hệ quả của việc dùng sai trục, đã kiểm chứng trên `backend/db/mirbase.db` (2 658 mature hsa):

* **Báo động giả:** `hsa-let-7a-5p` và `hsa-let-7b-5p` cùng seed `GAGGUAG` → seed-map báo "cùng họ",
  nhưng 3′-6mer khác nhau 2 nt (`ATAGTT` vs `GTGGTT`) → **RT primer không đụng nhau**.
* **Bỏ sót thật:** bucket 3′-6mer `CTGCAG` chứa **14 miRNA hsa với 14 seed khác nhau**
  (`hsa-miR-503-5p`, `hsa-miR-4722-3p`, `hsa-miR-4742-3p`, `hsa-miR-6510-3p`, …).
  RT primer của chúng **giống hệt nhau từng byte**. Seed-map hoàn toàn im lặng.
  Các bucket lớn khác: `CCCCAG` (29 seed), `TCCCAG` (16), `CCACAG` (15), `TTTTGC` (11).

Chính `benchmark/family_grouping_validation.json` đã thừa nhận điều này. SPEC này biến sự thừa nhận
đó thành code.

### 0.2 Phạm vi

| ID | Hạng mục | Ưu tiên | Ước lượng |
|---|---|---|---|
| **P1** | 3′-overhang collision map + sửa hình học Kwok + chuyển trục scoring | 1 | 3–4 ngày |
| **P2** | Reproducibility của validation block + thu hẹp caveat LNA | 2 | 0.5 ngày |
| **P3** | Cờ 3′-isomiR (dữ liệu + module + UI) | 3 | 1.5 ngày |
| **P4** | Trình ΔG / khoảng bất định thay cho Tm điểm của duplex 6 nt | 4 | 1 ngày |
| **P5** | 3 finding cosmetic (guard bound, cột CSV, species_note) | 5 | 1 giờ |
| **P6** | Intake spec thí nghiệm wet-lab D.2 (không code, chỉ tài liệu + schema) | dài hạn | 0.5 ngày |

### 0.3 Bất biến — KHÔNG được phá

1. **`OVERHANG_LENGTH_DEFAULT = 6`.** Vùng bám RT cố định 6 nt (Chen 2005). Mọi giá trị ≠ 6 phải
   tiếp tục kèm `off_label_warning`.
2. **`UNIVERSAL_REVERSE` giữ nguyên chuỗi `5'-CCAGTGCAGGGTCCGAGGTA-3'`.**
3. **Không thêm dependency mới** ngoài stack đã cố định (Flask 3, flask-cors, requests, primer3-py,
   ViennaRNA optional / React 18, Vite 5, Tailwind 3, React Router v6, Axios). Module mới chỉ dùng
   stdlib.
4. **Không có network call lúc runtime request.** Mọi dữ liệu miRBase phải là file tĩnh build offline.
5. **Không được biến khẳng định tất định thành tuyên bố hiệu năng.** Chuỗi "123/123 checks" và
   "50/50 design success" phải giữ nhãn *deterministic correctness*, tuyệt đối không được đổi thành
   "validated performance", "accuracy", hay "benchmark". Xem §2.3.
6. **Mọi con số nhiệt động in ra UI phải kèm chemistry + accuracy label.** Không có ngoại lệ.
7. **Backward compatibility của API:** key `specificity_warnings.cross_reactivity` phải tiếp tục tồn
   tại với schema cũ. Trục mới được **thêm vào**, không thay thế.

### 0.4 Thứ tự commit bắt buộc

```
C1  feat(specificity): add kwok.py with primer-anchored geometry + tests
C2  fix(specificity): correct Kwok weighting direction in family_crossreactivity
C3  feat(data): build_overhang_index.py -> mirbase_overhang_index.json
C4  feat(specificity): overhang_collision.py (RT + FWD dual-axis) + tests
C5  feat(scoring): move family_discrimination to 3' RT axis
C6  feat(api): expose specificity_warnings.overhang_collision
C7  feat(ui): OverhangCollisionPanel + demote seed map to biological context
C8  feat(export): dual-axis specificity in CSV/PDF/FASTA
C9  fix(validation): committed build_benchmark_validation.py (Finding #1)
C10 fix(lna): narrow benchmark caveat to single-LNA (Finding #2)
C11 feat(isomir): 3' isomiR advisory data + module + UI
C12 refactor(thermo): report dG/uncertainty instead of point Tm for 6-nt duplex
C13 fix: cosmetic findings #3 #4 #5
C14 docs: wet-lab D.2 intake spec
```

Mỗi commit phải **xanh test** trước khi sang commit kế. C2 và C5 làm đổi kết quả số → bắt buộc
re-run §7.2 sau mỗi commit đó.

---

## 1. P1 — 3′-Overhang Collision Map (ưu tiên #1)

### 1.1 P1.0 — Sửa hình học Kwok (bắt buộc làm TRƯỚC)

**Phát hiện mới (Finding #6), đã verify trên code hiện tại.**

`family_crossreactivity._kwok_distance()` (`family_crossreactivity.py:261`) tính:

```python
for i, (c1, c2) in enumerate(zip(reversed(s1), reversed(s2))):
    w = KWOK_POSITION_WEIGHTS[i]      # i = 0 -> nt cuối 3' của miRNA
```

`KWOK_POSITION_WEIGHTS = [4.0, 2.0, 1.5, 1.0, 1.0, 1.0]` (constants.py:578) mô tả *"mismatch tại
đầu 3′ của **primer** chặn extension"* [Kwok90]. Nhưng code áp trọng số lên **đầu 3′ của miRNA**.
Hai đầu này **ngược nhau**.

**Chứng minh hình học.** Gọi mature miRNA dài `L`, cửa sổ overhang là các vị trí `L-5 … L` (1-based),
ký hiệu `N1 … N6` với `N6` là nt tận cùng 3′:

```
miRNA   5'- … N1 N2 N3 N4 N5 N6 -3'
RT prim      3'- c1 c2 c3 c4 c5 c6 -5'      (cK = complement of NK)
```

Viết RT primer theo chiều 5′→3′: `5'-c6 c5 c4 c3 c2 c1-3'`. Vậy **đầu 3′ của RT primer = `c1`, bắt
cặp với `N1`, tức nt 5′-*most* của cửa sổ overhang** — KHÔNG phải `N6`. Reverse transcriptase kéo
dài từ `c1` về phía 5′ của miRNA. Do đó mismatch tại `N1` mới là mismatch chặn extension.

Với forward primer thì ngược lại: vùng đặc hiệu = `mature[0:L_spec]`, primer cùng chiều với miRNA,
nên **đầu 3′ của forward primer = vị trí `L_spec`, tức nt 3′-most của cửa sổ prefix**.

**Chỉ thị.**

Tạo `backend/algorithm/specificity_check/kwok.py`:

```python
"""
kwok.py — position-weighted mismatch distance, anchored to the PRIMER 3' terminus.

[Kwok90] Kwok S et al. Nucleic Acids Res 1990;18(4):999-1005 — a mismatch at or near
the primer 3' terminus blocks polymerase extension; a mismatch near the primer 5' end
is largely tolerated.

Geometry note (this is the whole point of the module):
  The weight index MUST be counted from the primer's 3' terminus, not from the miRNA's
  3' end. For the two primer classes in stem-loop RT-qPCR these map to OPPOSITE ends of
  the miRNA window:

    RT primer  = revcomp(mature[-N:])      -> primer 3' terminus pairs with window[0]
                                              (the 5'-most nt of the 3' overhang window)
    FWD primer = mature[:L] (same sense)   -> primer 3' terminus is window[L-1]
                                              (the 3'-most nt of the 5' prefix window)
"""

from ..constants import KWOK_POSITION_WEIGHTS

PRIMER_3P_AT_WINDOW_START = "window_start"   # RT primer
PRIMER_3P_AT_WINDOW_END   = "window_end"     # forward primer


def kwok_weighted_distance(a: str, b: str, primer_3prime_at: str) -> float:
    """
    Position-weighted mismatch distance between two equal-length windows.

    Args:
        a, b: equal-length sequence windows (same alphabet, same orientation).
        primer_3prime_at: PRIMER_3P_AT_WINDOW_START (RT) or
                          PRIMER_3P_AT_WINDOW_END (forward).

    Returns 0.0 when lengths differ (caller must handle that case explicitly).
    Higher value = mismatches sit closer to the primer 3' terminus = better
    discrimination = LESS likely to co-amplify.
    """
```

Quy tắc cài đặt:

* `primer_3prime_at == PRIMER_3P_AT_WINDOW_START` → duyệt `enumerate(zip(a, b))`, index 0 = ký tự đầu.
* `primer_3prime_at == PRIMER_3P_AT_WINDOW_END`   → duyệt `enumerate(zip(reversed(a), reversed(b)))`.
* Index vượt `len(KWOK_POSITION_WEIGHTS)` → weight `1.0`.
* `ValueError` nếu `primer_3prime_at` không thuộc 2 hằng số trên.

Cập nhật `constants.py:573-579` — sửa comment cho đúng, **giữ nguyên giá trị số**:

```python
# [Kwok90] Position-weighted mismatch distance, indexed from the PRIMER 3' TERMINUS.
# Weight[i] = contribution of a mismatch i positions away from the primer 3' end
# (0 = the 3'-terminal base pair). A 3'-terminal mismatch blocks extension [Kwok90 Fig.3].
# WARNING: for the stem-loop RT primer the primer 3' terminus pairs with the 5'-MOST
# nucleotide of the miRNA 3' overhang window (the RT primer is the reverse complement).
# Always go through specificity_check.kwok.kwok_weighted_distance() — never index this
# list directly.
KWOK_POSITION_WEIGHTS    = [4.0, 2.0, 1.5, 1.0, 1.0, 1.0]
KWOK_DIST_DISCRIMINATING = 3.0
```

Sửa `family_crossreactivity._kwok_distance` → gọi
`kwok_weighted_distance(s1, s2, PRIMER_3P_AT_WINDOW_START)`. Giữ tên hàm cũ như wrapper mỏng để
không vỡ import.

**Tác động số học (đã tính sẵn, dùng làm test vector).** Target `hsa-let-7a-5p`, window DNA `ATAGTT`:

| Sibling | window | mismatch | kwok **đúng** | kwok **cũ (sai)** |
|---|---|---|---|---|
| let-7b-5p | `GTGGTT` | 2 | **5.5** | 2.0 |
| let-7c-5p | `ATGGTT` | 1 | **1.5** | 1.0 |
| let-7g-5p | `ACAGTT` | 1 | **2.0** | 1.0 |
| let-7i-5p | `GCTGTT` | 3 | **7.5** | 3.0 |
| let-7d/e/f-5p | `ATAGTT` | 0 | **0.0** | 0.0 |

Cập nhật `backend/tests/test_kwok_family.py`: các test đang khẳng định "3′-terminal mismatch → 4.0"
đang mô tả *miRNA* 3′ end. Viết lại theo ngữ nghĩa primer, dùng đúng bảng trên làm expected values.
**Không được xoá test — phải viết lại và ghi lý do trong docstring của module test.**

### 1.2 P1.1 — Data build: `mirbase_overhang_index.json`

Tạo `backend/scripts/build_overhang_index.py`. Tái dùng cache `backend/scripts/.mirbase_cache/mature.fa`
và hàm `parse_mature_fa()` của `build_mirbase_data.py` (import, không copy-paste).

**Output:** `backend/data/mirbase_overhang_index.json`

```json
{
  "_metadata": {
    "description": "Full per-species mature miRNA index for primer-axis collision analysis (RT 3' overhang and forward 5' prefix). NOT a family/seed grouping.",
    "source": "miRBase CURRENT - https://mirbase.org/download/mature.fa",
    "mirbase_release": "<parsed or 'unknown'>",
    "build_date": "YYYY-MM-DD",
    "species": ["hsa", "mmu", "rno"],
    "n_mirnas": {"hsa": 2658, "mmu": 0, "rno": 0},
    "axes": {
      "rt": "mature[-6:] (RNA). RT primer 3' segment = revcomp(dna(window)).",
      "fwd": "mature[0:L] (RNA), L = forward primer specific_length, resolved at runtime."
    },
    "provenance": "generated",
    "warning": "Re-run scripts/build_overhang_index.py after every miRBase release update."
  },
  "mature": {
    "hsa": {"hsa-miR-21-5p": "UAGCUUAUCAGACUGAUGUUGA", "...": "..."},
    "mmu": {},
    "rno": {}
  }
}
```

Yêu cầu:

* CLI khớp `build_mirbase_data.py`: `--species hsa,mmu,rno` (mặc định `hsa,mmu,rno`), `--no-download`,
  `--out`.
* **Chỉ lưu `mature`** — bucket theo 6-mer được dựng **trong bộ nhớ** lúc load module (§1.3) để
  không có hai nguồn sự thật.
* In summary ra stdout: số miRNA mỗi loài, số bucket 3′-6mer, kích thước bucket lớn nhất, và
  *"largest RT-collision bucket: `<key>` with `<n>` members across `<k>` distinct seeds"* — con số này
  là bằng chứng trực tiếp cho GAP #1, cần cho báo cáo.
* Test `backend/tests/scripts/test_build_overhang_index.py` chạy trên fixture
  `backend/tests/fixtures/mature_mock.fa` (đã có), assert schema + species filter + xác định
  bucket đúng.

### 1.3 P1.2 — Module `overhang_collision.py`

Tạo `backend/algorithm/specificity_check/overhang_collision.py`.

#### Chữ ký

```python
def check_overhang_collision(
    mature_seq: str,
    mirna_name: str,
    params: dict,
    overhang_len: int = 6,
    forward_specific_len: int | None = None,
    species: str | None = None,
    max_report: int = 25,
) -> dict:
```

* `forward_specific_len`: lấy từ candidate rank #1 (`top_n[0]["specific_length"]`). Nếu `None` →
  dùng `FWD_PREFIX_LEN_FALLBACK = 12` và set `"forward_axis_estimated": true`.
  (12 là cận dưới của `specific_lengths = [12..17]` trong `forward_primer.py` — chọn cận dưới là
  **bảo thủ**: prefix ngắn hơn → ít mismatch hơn → báo cáo nhiều collider hơn, không bỏ sót.)
* `species`: resolve bằng đúng logic `family_crossreactivity._resolve_species_prefix()` — **import
  và tái dùng**, không viết lại.

#### Thuật toán

1. Load index (cache module-level, giống `_load_db()`), lấy `mature[species]`.
2. Loại chính target khỏi tập screen (so khớp theo tên **và** theo chuỗi — miRBase có tên khác nhau
   cùng chuỗi).
3. Với mỗi collider:
   * `rt_mm = hamming(dna(target[-N:]), dna(other[-N:]))`; bỏ qua nếu `rt_mm > RT_MM_REPORT_MAX = 2`
     **và** `fwd_mm > FWD_MM_REPORT_MAX = 2`. (Bỏ sớm để O(n) rẻ; n ≈ 2 700 → < 5 ms.)
   * `rt_kwok = kwok_weighted_distance(win_t, win_o, PRIMER_3P_AT_WINDOW_START)`
   * `fwd_mm  = hamming(dna(target[:L]), dna(other[:L]))` — nếu `len(other) < L`, so trên phần chồng
     lấn và đặt `"forward_truncated": true`.
   * `fwd_kwok = kwok_weighted_distance(pre_t, pre_o, PRIMER_3P_AT_WINDOW_END)`
   * `same_seed_family = get_family_id(target) == get_family_id(other)` (import từ
     `family_crossreactivity`) — chỉ để hiển thị đối chiếu, **không dùng để phân loại**.
4. Phân loại từng trục bằng cùng một hàm thuần:

```python
def _axis_risk(mismatch: int, kwok: float) -> str:
    if mismatch == 0:                                   return "IDENTICAL"
    if mismatch == 1:
        return "LOW" if kwok >= KWOK_DIST_DISCRIMINATING else "HIGH"
    if mismatch == 2:                                   return "LOW"
    return "SAFE"
```

5. **Combined risk — đây là điểm khoa học trung tâm của P1.** Assay chỉ khuếch đại off-target khi
   *cả hai* trục đều không phân biệt được. Đặc hiệu tổng = RT capture × forward discrimination.

```
                 FWD: IDENTICAL/HIGH      FWD: LOW        FWD: SAFE
RT: IDENTICAL         CRITICAL              LOW             SAFE
RT: HIGH              CRITICAL              LOW             SAFE
RT: LOW               LOW                   SAFE            SAFE
RT: SAFE              SAFE                  SAFE            SAFE
```

Cài đặt dưới dạng `dict` hằng `COMBINED_RISK_MATRIX` trong `constants.py`, không phải chuỗi `if`.

6. Báo cáo: giữ mọi entry có `combined_risk != "SAFE"`, **cộng thêm** mọi entry có
   `rt_risk == "IDENTICAL"` kể cả khi combined = SAFE (cần cho multiplex / pooling RT primer).
   Sắp xếp: `CRITICAL` → `LOW`; trong cùng bậc, `rt_mm` tăng dần rồi `fwd_mm` tăng dần.
   Cắt ở `max_report`, và set `"truncated": true` + `"n_total_non_safe"` khi bị cắt.

#### Schema trả về

```python
{
  "axis_model": "dual",
  "species": "hsa",
  "overhang_len": 6,
  "forward_specific_len": 12,
  "forward_axis_estimated": False,
  "target": {
    "name": "hsa-let-7a-5p",
    "rt_window_rna": "AUAGUU",              # RNA, 6 nt cuối của mature
    "rt_window_dna": "ATAGTT",
    "rt_primer_3prime_segment": "AACTAT",   # = revcomp(rt_window_dna)
    "fwd_window_dna": "TGAGGTAGTAGG"
  },
  "n_screened": 2657,
  "collisions": [
    {
      "mirna": "hsa-let-7d-5p",
      "rt_window_dna": "ATAGTT",
      "rt_mismatch": 0,
      "rt_kwok": 0.0,
      "rt_risk": "IDENTICAL",
      "fwd_window_dna": "AGAGGTAGTAGG",
      "fwd_mismatch": 1,
      "fwd_mismatch_positions_1based": [1],
      "fwd_kwok": 1.0,
      "fwd_risk": "HIGH",
      "combined_risk": "CRITICAL",
      "same_seed_family": True,
      "note": "RT primer is byte-identical; the only discriminator is the forward primer, whose single mismatch sits at position 1 (forward 5' end) where it is tolerated."
    }
  ],
  "summary": {"CRITICAL": 1, "LOW": 3, "rt_identical": 3, "n_reported": 4, "truncated": False},
  "worst_rt_risk": "IDENTICAL",
  "worst_combined_risk": "CRITICAL",
  "recommendation": { ... },        # §1.4
  "data_provenance": {"source": "...", "build_date": "...", "mirbase_release": "...", "n_screened": 2657},
  "interpretation": "Specificity of stem-loop RT-qPCR is the product of two independent axes: the RT primer binds the 3'-terminal 6 nt, the forward primer binds the 5' region. An off-target is co-amplified only when BOTH axes fail. Seed-family membership (positions 2-8) is a biological mRNA-targeting axis and is reported separately for context only."
}
```

#### Khuyến nghị (`recommendation`)

Không tự tiện nới overhang. Logic:

* `worst_combined_risk == "SAFE"` → `{"action": "none", ...}`.
* `CRITICAL` với `rt_risk` IDENTICAL/HIGH và `fwd_risk` IDENTICAL/HIGH:
  1. Thử `overhang_len` 7 rồi 8 (trần `_OVERHANG_MAX_NT = 8`); nếu giải quyết được → đề xuất, **kèm
     nguyên văn `off_label_warning` hiện có** (Chen 2005 chỉ test 6 nt).
  2. Nếu không → thử tăng `forward_specific_len` sao cho vị trí mismatch của collider rơi vào 3 nt
     cuối của forward primer (`kwok ≥ KWOK_DIST_DISCRIMINATING`); trả về `suggested_forward_specific_len`.
  3. Nếu vẫn không → `{"action": "orthogonal_assay", "reason": "..."}` với thông điệp thẳng thắn:
     hai miRNA này không phân biệt được bằng stem-loop RT-qPCR đơn thuần; cần TaqMan probe bắc qua
     vùng khác biệt, LNA, hoặc phương pháp khác.
* **Không bao giờ** đề xuất giải pháp mà module không kiểm chứng được bằng tính toán trong chính
  response đó.

#### Hằng số mới (`constants.py`, SECTION mới cuối file)

```python
# ---- Primer-axis collision analysis (Week 2 P1) -------------------
RT_MM_REPORT_MAX          = 2      # report RT-axis colliders with <= 2 mismatches in the window
FWD_MM_REPORT_MAX         = 2      # report FWD-axis colliders with <= 2 mismatches in the prefix
FWD_PREFIX_LEN_FALLBACK   = 12     # used when forward specific_length is unavailable
COLLISION_MAX_REPORT      = 25     # cap rows returned to the client
COMBINED_RISK_MATRIX      = { ... }   # see SPEC_week2 §1.3 step 5
COMBINED_RISK_SCORE       = {"SAFE": 100, "LOW": 70, "CRITICAL": 0, "no_index_data": 100}
```

### 1.4 P1.3 — Test vector bắt buộc (giá trị thật, đã verify trên `mirbase.db`)

Tạo `backend/tests/test_overhang_collision.py`. Ba fixture dưới đây là **ground truth**, không được
sửa số:

**Fixture A — `hsa-let-7a-5p` (`UGAGGUAGUAGGUUGUAUAGUU`), overhang 6, `L_spec = 12`**

| Collider | rt_window | rt_mm | rt_kwok | fwd_mm | fwd_mm_pos | combined | Vì sao quan trọng |
|---|---|---|---|---|---|---|---|
| let-7d-5p | `ATAGTT` | 0 | 0.0 | 1 | [1] | **CRITICAL** | mismatch ở 5′ forward → không phân biệt |
| let-7e-5p | `ATAGTT` | 0 | 0.0 | 1 | [9] | **CRITICAL** | mismatch giữa → yếu |
| let-7f-5p | `ATAGTT` | 0 | 0.0 | 1 | [12] | **LOW** | mismatch đúng đầu 3′ forward → phân biệt tốt |
| let-7b-5p | `GTGGTT` | 2 | 5.5 | 0 | [] | **LOW** | RT là discriminator DUY NHẤT |
| let-7c-5p | `ATGGTT` | 1 | 1.5 | 0 | [] | **CRITICAL** | rt_kwok < 3.0 → RT không phân biệt, forward giống hệt |
| let-7g-5p | `ACAGTT` | 1 | 2.0 | 1 | [12] | **LOW** | |
| let-7i-5p | `GCTGTT` | 3 | 7.5 | 1 | [12] | **SAFE** (không report) | |

> Ghi chú cho implementer: hàng let-7b là bằng chứng phản bác trực tiếp cho seed-map — cùng seed,
> forward giống hệt 12/12, **chỉ RT axis cứu được assay**. Hàng let-7c là ca nguy hiểm nhất và
> seed-map hiện tại đang xếp nó ngang hàng với let-7b.

**Fixture B — `hsa-miR-503-5p` (`UAGCAGCGGGAACAGUUCUGCAG`), bucket `CTGCAG`**

Phải phát hiện ≥ 5 collider `rt_mismatch == 0` **có seed khác nhau**, gồm ít nhất:
`hsa-miR-4722-3p` (fwd_mm=9), `hsa-miR-4742-3p` (11), `hsa-miR-6510-3p` (9), `hsa-miR-6744-3p` (9),
`hsa-miR-6788-3p` (11).

Theo ma trận §1.3: `rt_risk == "IDENTICAL"` × `fwd_risk == "SAFE"` → **`combined_risk == "SAFE"`**.
Chúng vẫn **phải xuất hiện trong `collisions`** nhờ quy tắc *"luôn báo cáo entry có
`rt_risk == IDENTICAL`"* (§1.3 bước 6), với `summary["rt_identical"] >= 5`,
`worst_combined_risk == "SAFE"`, và `same_seed_family == False` cho tất cả.
Đây chính là ca "RT primer giống hệt nhau nhưng assay vẫn đặc hiệu nhờ forward primer" — thông tin
bắt buộc phải hiển thị (quan trọng khi pool RT primer trong multiplex) nhưng **không** được tính là
lỗi thiết kế.
**Assert bổ sung:** `check_family_crossreactivity()` trên cùng input trả về **0** trong số các miRNA
này → chứng minh bằng test rằng seed-map bỏ sót. Đặt tên test
`test_seed_map_misses_rt_axis_colliders`.

**Fixture C — `hsa-miR-21-5p` (`UAGCUUAUCAGACUGAUGUUGA`)**

`rt_window = TGTTGA`; **không có** collider `rt_mismatch == 0` trong hsa. Có 22 collider
`rt_mismatch == 1`, trong đó `hsa-miR-425-5p` (`CGTTGA`, rt_kwok = 4.0), `hsa-miR-4778-3p`
(`AGTTGA`, 4.0), `hsa-miR-6870-5p` (`GGTTGA`, 4.0) → `rt_risk == "LOW"` nhờ Kwok, tất cả
`combined_risk == "SAFE"`. Assert `worst_combined_risk == "SAFE"` và `summary["CRITICAL"] == 0`.

**Test hiệu năng:** `check_overhang_collision` trên hsa (2 658 seq) phải < 50 ms trên CI
(`pytest --durations`). Nếu vượt, dựng bucket index 1 lần ở module load thay vì scan.

### 1.5 P1.4 — Scoring: chuyển `family_discrimination` sang trục 3′

Theo quyết định của maintainer: tiêu chí `family_discrimination` trong `SCORING_WEIGHTS_V4` **giữ
nguyên key và trọng số**, nhưng **nguồn risk đổi từ seed-family sang `worst_combined_risk`**.

Trong `scoring.py`:

* `score_candidate()` nhận thêm tham số `overhang_collision: dict | None = None`.
* Thay `_extract_worst_family_risk(cross_reactivity)` bằng
  `_extract_worst_primer_axis_risk(overhang_collision)`:
  * `None` hoặc thiếu index → `"no_index_data"` → 100 điểm, và explanation **phải** ghi rõ
    "no overhang index available — this criterion did not contribute discriminating information".
  * ngược lại → `overhang_collision["worst_combined_risk"]` map qua `COMBINED_RISK_SCORE`.
* `explanations["family_discrimination"]` viết lại, phải nêu: trục dùng (RT 3′ overhang + FWD 5′
  prefix), số collider CRITICAL, tên collider tệ nhất, và một câu nói rõ seed-family **không** được
  dùng để chấm điểm.
* Giữ `FAMILY_DISCRIMINATION_RISK_SCORE` trong `constants.py` (còn dùng cho panel ngữ cảnh sinh học)
  nhưng thêm comment `# legacy: seed-axis, informational only — scoring uses COMBINED_RISK_SCORE`.

`design_pipeline.py`:

* Gọi `check_overhang_collision()` **một lần** trước vòng scoring (giống `cross_reactivity_shared`),
  với `forward_specific_len` = `specific_length` của candidate tốt nhất theo điểm thô. Vì có phụ
  thuộc vòng (điểm ↔ L_spec), dùng quy tắc: **pass 1** tính collision với
  `FWD_PREFIX_LEN_FALLBACK`, chấm điểm, lấy `top_n[0]["specific_length"]`, **pass 2** tính lại
  collision với L thật và chấm điểm lại. Chỉ 2 pass, không lặp. Ghi
  `"forward_axis_refined": true` vào metadata.
* Thêm `global_warnings` mới `field: "overhang_collision"`, severity `"critical"` khi có ≥ 1
  `CRITICAL`, `"warning"` khi chỉ có `rt_identical > 0`.
* **Giữ nguyên** warning `field: "cross_reactivity"` hiện có nhưng đổi message thành ngữ cảnh sinh
  học: `"Seed family <X> shares the mRNA-targeting seed (positions 2-8). This is NOT the primer
  specificity axis — see overhang_collision for RT/forward binding-site analysis."`
  và hạ severity xuống `"info"`.

### 1.6 P1.5 — API

`design_pipeline` trả về:

```python
"specificity_warnings": {
    "cross_reactivity": cross_reactivity,          # UNCHANGED schema (bất biến §0.3.7)
    "overhang_collision": overhang_collision,      # NEW
    "axis_note": (
        "cross_reactivity = seed-based grouping (mRNA-targeting axis, biological context). "
        "overhang_collision = primer binding axes (RT 3' overhang + forward 5' prefix). "
        "Only overhang_collision drives warnings and scoring."
    ),
    "data_note": "..."   # cập nhật để nhắc build_overhang_index.py
}
```

Cập nhật `backend/static/openapi.yaml` cho schema mới; `backend/tests/test_openapi_sync.py` phải
tiếp tục xanh (test này đang kiểm tra đồng bộ — đọc nó trước khi sửa yaml).

### 1.7 P1.6 — Frontend

**Component mới:** `frontend/src/components/OverhangCollisionPanel.jsx`

* Props: `{ overhangCollision }`. Không gọi backend.
* Header: `Primer Binding Specificity` + badge `RT 3′ · 6 nt` và `FWD 5′ · {L} nt`; badge provenance
  (build_date + n_screened) theo đúng style `ProvenanceBadge` hiện có.
* **Visual chính — ma trận 2 trục** (SVG thuần, không thư viện): trục X = FWD risk
  (SAFE→IDENTICAL), trục Y = RT risk. Mỗi collider là 1 điểm; ô góc trên-phải là vùng CRITICAL
  (nền `#FEF2F2`). Hover → panel chi tiết hiện `rt_window`, `fwd_window` với các nt mismatch in đậm
  đỏ, `rt_kwok`, `fwd_kwok`, `note`.
* Toggle `Matrix | Table` giống `FamilySpecificityMap`. Bảng gồm cột: Collider · RT 6-mer · RT mm ·
  RT risk · FWD mm · FWD mm pos · FWD risk · **Combined** · Same seed?
* Màu: tái dùng đúng palette `RISK_CONFIG` hiện có; thêm `CRITICAL` = `#7F1D1D` / bg `#FEF2F2`.
* Empty state: `"No primer-axis collision detected across {n_screened} {species} mature miRNAs
  (RT 3′-{N}mer and forward 5′-{L}mer both discriminate)."`

**Sửa `FamilySpecificityMap.jsx`:**

* Đổi tiêu đề thành `Seed Family (biological context)`.
* Thêm ngay dưới tiêu đề một dòng cố định, không ẩn được:
  `"Seed grouping (positions 2–8) is the mRNA-targeting axis. It does not determine primer
  specificity — see Primer Binding Specificity above."`
* **Xoá `recommendation` block** khỏi component này (khuyến nghị giờ thuộc về
  `OverhangCollisionPanel`); giữ dữ liệu trong API cho back-compat.
* Giữ nguyên map/table nhưng đổi nhãn cột `Risk` → `Seed similarity` và đổi giá trị hiển thị
  `IDENTICAL/HIGH/LOW/SAFE` → `identical 3′ / near / distant` để **không** dùng lại từ vựng risk.

**`ResultsSection/index.jsx`:** render `OverhangCollisionPanel` **phía trên** `FamilySpecificityMap`.

### 1.8 P1.7 — Export

`backend/routes/export.py`:

* CSV: thêm cột `rt_axis_worst_risk`, `fwd_axis_worst_risk`, `combined_worst_risk`,
  `n_critical_colliders`, `top_critical_collider`.
* PDF (§ "Scientific caveats"): thêm nguyên văn `interpretation` của `overhang_collision`.
* Sửa `_family_provenance_note()` (dòng ~621) để nói rõ seed-family là ngữ cảnh sinh học.
* FASTA header: không đổi.
* `backend/tests/test_export_checklist.py` phải được mở rộng để assert 5 cột mới xuất hiện.

---

## 2. P2 — Reproducibility & Provenance

### 2.1 Finding #1 — validation block phải tái lập được bằng code committed

**Hiện trạng đã verify:** `benchmark/benchmark_results.json` có key `validation` (12 field) nhưng
không script nào trong repo sinh ra nó. `validation/validate_primers.py` chỉ ghi
`validation/results.csv` + `validation/results.json`; `benchmark/run_benchmark.py` chỉ ghi markdown
(`benchmark/compare_tools.md`). Bước merge đã làm thủ công bằng Bash và không commit → chạy lại
đúng lệnh "reproduce" trong README sẽ **không** dựng lại được trang Benchmark.

**Chỉ thị.** Tạo `validation/build_benchmark_validation.py`:

```
Usage:
  python validation/build_benchmark_validation.py \
      --results validation/results.json \
      --benchmark benchmark/benchmark_results.json \
      [--in-place] [--check]
```

* Đọc `results.json`, dựng đúng khối `validation` mà `frontend/src/pages/BenchmarkPage.jsx` đang
  đọc (`purpose`, `run_date`, `method`, `sources`, `checks_passed`, `checks_total`, `success_rate`,
  `deterministic_primer_targets`, …). **Đọc BenchmarkPage.jsx trước khi viết** để lấy đúng tên field;
  không được đoán.
* `--in-place` ghi đè key `validation` trong `benchmark_results.json`, giữ nguyên `_metadata`,
  `metrics`, `per_assay` (dùng `json.load` → sửa key → `json.dump(indent=2, ensure_ascii=False)`).
* `--check` (dùng cho CI): dựng lại trong bộ nhớ và so với file trên đĩa; khác → exit 1 kèm diff.
* Ghi `validation["generated_by"] = "validation/build_benchmark_validation.py"` và
  `validation["source_file"] = "validation/results.json"`.

Cập nhật `README.md` + `validation/VALIDATION_PLAN.md` với chuỗi lệnh tái lập **đầy đủ, chạy được
copy-paste**:

```bash
cd backend && python app.py &                 # Terminal 1
python validation/validate_primers.py --base-url http://localhost:5000
python validation/build_benchmark_validation.py --in-place
```

Thêm job vào `.github/workflows/test_phase3.yml` (hoặc workflow mới) chạy
`build_benchmark_validation.py --check` để chặn drift.

### 2.2 Finding #2 — thu hẹp caveat LNA

`lna_tm.py:423-425` hiện gắn `_CAVEAT_VERIFY_TABLES` (chứa câu *"Benchmarked against McTigue 2004
Table 1 … ΔTm RMSD 0.78 °C"*) khi `method` chứa `"mctigue04"` **hoặc** `"owczarzy11"`. Nhưng
benchmark (`backend/tests/test_lna_benchmark.py`) chỉ phủ oligo **single-LNA**; bảng `owczarzy11`
chỉ được dùng cho doublet `lna_lna` (hai LNA liền kề) — nằm ngoài phạm vi benchmark. Đây là
over-claim provenance.

**Chỉ thị.** Tách thành hai chuỗi:

```python
_CAVEAT_BENCHMARKED_SINGLE_LNA = (
    "LNA NN parameters: Owczarzy 2011 Table 2 (single-LNA set derived from McTigue 2004 32NN). "
    "Benchmarked against McTigue 2004 Table 1 measured Tm (delta-Tm RMSD 0.78 C, absolute Tm RMSD "
    "1.54 C; 1 M Na+). Predictions away from ~1 M Na+ rely on the SantaLucia 1998 salt model - "
    "verify with your synthesis provider for final designs."
)
_CAVEAT_CONSECUTIVE_LNA_UNBENCHMARKED = (
    "This design contains CONSECUTIVE LNA positions. The adjacent-LNA (LNA:LNA) nearest-neighbour "
    "parameters come from Owczarzy 2011 and are NOT covered by our benchmark, which contains "
    "single-LNA oligos only. Treat the predicted Tm for these designs as an unvalidated estimate."
)
```

Logic thay thế cho dòng 423-425:

```python
warnings.append(_CAVEAT_LNA_GENERAL)
if "mctigue04" in method:
    warnings.append(_CAVEAT_BENCHMARKED_SINGLE_LNA)
if "owczarzy11" in method:
    warnings.append(_CAVEAT_CONSECUTIVE_LNA_UNBENCHMARKED)
```

Áp dụng cùng nguyên tắc cho hai chỗ còn lại: dòng ~705-706 và ~562, ~728.
Thêm field `"benchmark_coverage": "single_lna" | "consecutive_lna_unbenchmarked" | "mixed"` vào dict
trả về để frontend (`LnaPanel/index.jsx`) hiển thị badge tương ứng.
Test mới trong `backend/tests/test_lna_tm.py`: oligo có LNA liền kề → warning chứa
`"NOT covered by our benchmark"`; oligo single-LNA → **không** chứa chuỗi đó.

### 2.3 Ngôn ngữ khẳng định (bắt buộc rà soát)

Grep toàn repo các chuỗi `123/123`, `50/50`, `100%`, `success rate`, `validated`, `benchmark`.
Với mỗi chỗ hiển thị cho người dùng, đảm bảo có nhãn phân biệt rõ:

* `deterministic correctness` — kiểm tra tất định (recompute độc lập), n = 8 target + 4 published.
* `design completion rate` — tỉ lệ pipeline trả về bộ primer hợp lệ, **không phải** hiệu suất PCR.
* Cấm tuyệt đối: `accuracy`, `validated performance`, `predicts efficiency` khi nói về hai con số này.

Thêm một dòng vào `BenchmarkPage.jsx` ngay dưới `checks_passed`:
`"Deterministic recomputation, not an efficiency benchmark. n = 8 targets (12 published-sequence
comparisons). No wet-lab efficiency data anchors these numbers — see Limitations."`

---

## 3. P3 — Cờ 3′-isomiR

### 3.1 Vấn đề

`isomir_flag.py` + `known_5prime_isomir_mirnas.json` chỉ phủ **5′-isomiR** (ảnh hưởng forward
primer). Nhưng lớp isomiR phổ biến nhất là **biến thể 3′** (thêm nucleotide templated/non-templated,
uridylation/adenylation) — rơi **chính xác vào cửa sổ 6 nt mà RT primer bám**. Hiện chỉ có một
advisory chung, vô điều kiện, gắn cho **mọi** miRNA (`stemloop_rt.py`, `field: "three_prime_isomir"`).
Advisory bật cho tất cả = không mang thông tin.

### 3.2 Dữ liệu

Tạo `backend/data/known_3prime_isomir_mirnas.json`, cùng cấu trúc `_metadata` + entry như file 5′:

```json
{
  "_metadata": {
    "description": "miRNAs with documented abundant 3'-isomiRs (templated 3' extension/truncation and non-templated uridylation/adenylation). The stem-loop RT primer binds the 3'-terminal 6 nt, so 3' heterogeneity directly reduces RT capture efficiency for the affected isoforms.",
    "version": "1.0.0",
    "isomir_type": "3prime - templated shift and/or non-templated addition at the 3' end",
    "sources": { "...": "PMID + DOI + full citation, same shape as the 5' file" },
    "evidence_levels": { "study_specific": "...", "review_supported": "..." },
    "coverage_warning": "Partial coverage. Absence of an entry does NOT mean the miRNA lacks 3' isomiRs."
  },
  "hsa-miR-21-5p": {
    "canonical": "UAGCUUAUCAGACUGAUGUUGA",
    "dominant_3prime_variants": ["+A", "+U", "-1"],
    "non_templated_addition": "adenylation",
    "isoform_fraction_estimate": 0.0,
    "evidence_level": "review_supported",
    "source": "<citation>",
    "rt_capture_impact": "moderate"
  }
}
```

**Chỉ thị nghiêm ngặt về dữ liệu:** không được bịa entry. Mỗi entry phải có PMID hoặc DOI thật, tra
được. Nguồn khuyến nghị để tra cứu: miRBase (read counts của isoform), isomiR-SEA / IsomiRmap
publications, Neilsen 2012 (Trends Genet), Wyman 2011 (Genome Res, non-templated addition),
Landgraf 2007. **Nếu không xác minh được ít nhất 8 entry có PMID, dừng lại và báo cáo — giao file
với entry chưa xác minh là vi phạm nặng hơn là giao file rỗng.** File có thể khởi tạo với chỉ
`_metadata` + entry đã xác minh.

### 3.3 Module

Mở rộng `isomir_flag.py` (không tạo module mới):

```python
def check_isomir_flag(mirna_name, forward_3prime_position) -> dict   # giữ nguyên, 5' axis
def check_3prime_isomir_flag(mirna_name, overhang_len=6) -> dict     # NEW
```

`check_3prime_isomir_flag` trả về:

```python
{
  "three_prime_isomir_risk": True,
  "mirna_name": "...",
  "overhang_len": 6,
  "dominant_3prime_variants": ["+A", "+U", "-1"],
  "rt_capture_impact": "moderate",
  "evidence_level": "review_supported",
  "warning": "This miRNA has documented 3' isomiRs. The stem-loop RT primer binds the 3'-terminal 6 nt, so 3'-variant isoforms are captured with reduced efficiency; measured abundance reflects the canonical 3' form more than total miRNA. Consider a 3'-tolerant chemistry or report the target as 'canonical 3' isoform'.",
  "data_warning": "<coverage_warning from _metadata>"
}
```

Không có entry → `three_prime_isomir_risk: False` + `note` nói rõ *absence of evidence ≠ evidence of
absence*, giống pattern của hàm 5′.

### 3.4 Nối vào pipeline

`stemloop_rt.py`:

* Gọi `check_3prime_isomir_flag(mirna_name, binding_len)`. **Cần truyền `mirna_name` vào
  `design_stemloop_rt()`** — hiện chưa có; thêm tham số `mirna_name: str = ""`, cập nhật caller
  trong `design_pipeline.py`.
* Advisory vô điều kiện hiện tại (`field: "three_prime_isomir"`, severity `info`):
  * có entry → severity `"warning"`, message = `warning` từ module, thêm `evidence_level`.
  * không có entry → giữ severity `"info"` nhưng rút gọn, và thêm
    `"coverage_note": "no entry in the 3' isomiR reference set"`.
* Thêm `"three_prime_isomir": <dict>` vào dict trả về của `design_stemloop_rt`.

Frontend: hiển thị trong `PrimerSetCard.jsx` (khối RT primer) như một dòng cảnh báo amber; không tạo
component mới. Export: thêm cột CSV `three_prime_isomir_risk` + `rt_capture_impact`.

Test `backend/tests/test_isomir_flag.py`: thêm case có entry / không entry / entry thiếu field
optional.

---

## 4. P4 — Bỏ Tm điểm cho duplex 6 nt

### 4.1 Vấn đề

`family_crossreactivity._calc_tm()` gọi `calculate_tm_nn()` trên overhang **6 nt** và
`stemloop_rt.py` (khối `USE_HYBRID_TM`) gọi `predict_hybrid_tm()` trên `overhang_rc` 6 nt. Mô hình
nearest-neighbour được hiệu chuẩn trên duplex dài; ở 6 nt, số hạng initiation và fraying đầu mút
chiếm tỉ trọng áp đảo → giá trị Tm điểm không đáng tin. Tool đã có short-duplex caveat (trung thực)
nhưng vẫn in một con số °C, và người đọc sẽ tin con số hơn caveat.

Về sinh học, mất mát thông tin bằng 0: RT stem-loop ủ ở nhiệt độ thấp / pulsed (16 °C → 30–42 °C
cycling, Chen 2005 / Kramer 2011), độ bám của overhang 6 nt được quyết định bởi hiệu ứng stacking
của stem-loop chứ không phải Tm của riêng 6 nt.

### 4.2 Chỉ thị

Thêm vào `backend/algorithm/thermodynamics.py`:

```python
SHORT_DUPLEX_NT_THRESHOLD = 8   # NN Tm is not reportable below this length

def duplex_dg_37(seq_dna: str, params: dict) -> dict:
    """
    Return dG37 (kcal/mol) for a short duplex plus an explicit reportability verdict.

    For duplexes shorter than SHORT_DUPLEX_NT_THRESHOLD the NN model's initiation term
    and end fraying dominate, so a point Tm is not a defensible number to display.
    We report dG37 (which remains useful for RELATIVE ranking of same-length windows)
    and an uncertainty band on Tm instead of a point value.
    """
    return {
        "dg37_kcal_mol": ...,
        "tm_point_c": ...,          # kept for internal ranking ONLY
        "tm_band_c": [lo, hi],      # tm_point +/- TM_SHORT_DUPLEX_UNCERTAINTY_C
        "reportable_as_tm": len(seq_dna) >= SHORT_DUPLEX_NT_THRESHOLD,
        "model": "SantaLucia 1998 NN",
        "caveat": "Nearest-neighbour parameters are calibrated on longer duplexes; below "
                  "8 bp the initiation term and terminal fraying dominate. Use dG37 for "
                  "relative ranking of equal-length windows, not the Tm as an absolute value.",
    }
```

`TM_SHORT_DUPLEX_UNCERTAINTY_C = 5.0` trong `constants.py` (± 5 °C; ghi rõ trong comment đây là
biên bảo thủ mang tính chỉ báo, không phải khoảng tin cậy thống kê).

Áp dụng:

* `family_crossreactivity._evaluate()` và `overhang_collision`: thay `tm_target_overhang` /
  `tm_sibling_overhang` / `delta_tm` bằng `dg37_target`, `dg37_collider`, `ddg37`. **Giữ**
  `delta_tm` trong response cho back-compat nhưng đổi thành `null` khi
  `reportable_as_tm == False`, và thêm `"delta_tm_deprecated_reason"`.
* `_classify_risk` hiện dùng ngưỡng `ΔTm ≥ 5.0 °C`. Chuyển sang `Δ(dG37) ≥ DDG_DISCRIMINATING`.
  Đặt `DDG_DISCRIMINATING = 1.5` kcal/mol và **ghi rõ trong comment rằng đây là ngưỡng heuristic
  chưa được neo bằng thực nghiệm** — nó sẽ là một trong các tham số cần calibrate ở GAP #4.
  Chạy lại Fixture A/B/C sau khi đổi và cập nhật expected values nếu phân loại đổi; nếu phân loại
  của Fixture A đổi so với bảng §1.4, **dừng và báo cáo** thay vì tự sửa bảng.
* `stemloop_rt.py`: `tm_hybrid_c` cho overhang 6 nt → set `None`, thêm `"tm_hybrid_band_c": [lo, hi]`
  và `"dg37_kcal_mol"`. `_tm_note` viết lại: nói rõ vì sao không in Tm điểm.
* UI (`ThermoTable.jsx`, `FamilySpecificityMap.jsx`, `OverhangCollisionPanel.jsx`): khi
  `reportable_as_tm == False` hiển thị `ΔG₃₇ = −6.1 kcal/mol` và `Tm ≈ 18 ± 5 °C (not reportable)`
  màu xám, **không** in `18.3 °C`.

---

## 5. P5 — Ba finding cosmetic

| # | File | Sửa |
|---|---|---|
| 3 | `backend/routes/analyze.py:253-256` | Guard `if not (15 <= len(mature) <= 30)` nhưng message ghi `"expected 17–24 nt"`. **Giữ bound 15–30** (chấp nhận isomiR/edge case) và sửa message thành: `"matureSequence length {n} nt is outside the accepted range (15–30 nt). Canonical mature miRNAs are 17–24 nt."` — bound và message phải khớp nhau. |
| 4 | `validation/validate_primers.py` (khối `cols`) | Cột `published_forward_match` không bao giờ được set (row set `published_forward_exact`). Đổi tên cột trong list `cols` thành `published_forward_exact` và **thêm** `published_forward_specific_shared`, `forward_specific_overlap_nt` để CSV không nghèo hơn JSON. |
| 5 | `backend/scripts/build_mirbase_data.py:234-239` | Với `--species hsa,mmu,rno`, `species_note` trở thành literal `"hsa,mmu,rno"` trong provenance. Xử lý multi-token: map từng prefix qua bảng `{"hsa": "human", "mmu": "mouse", "rno": "rat"}` và join → `"human (hsa), mouse (mmu), rat (rno)"`; prefix lạ giữ nguyên mã. Áp dụng cùng logic cho `build_overhang_index.py`. |

Mỗi mục kèm 1 test hồi quy. Finding #4 phải có test đọc CSV sinh ra và assert cột không rỗng khi
entry có `published_forward`.

---

## 6. P6 — GAP #4: Intake spec thí nghiệm wet-lab D.2 (tài liệu, chưa code)

### 6.1 Vì sao cần

Score V4 và "design success 100%" đều là in-silico. Không có một điểm dữ liệu efficiency nào neo
15 trọng số của `SCORING_WEIGHTS_V4`, ngưỡng `KWOK_DIST_DISCRIMINATING = 3.0`, hay
`DDG_DISCRIMINATING` mới ở §4. Đây là gap nền tảng lớn nhất còn lại; P1–P5 sửa *tính đúng của cơ
chế*, chỉ wet-lab mới sửa được *tính đúng của hiệu chuẩn*.

### 6.2 Thiết kế D.2 — bắt buộc gồm ca thất bại

Sai lầm phổ biến nhất là chỉ chạy top-1 của mỗi miRNA. Khi đó mọi assay đều tốt, phương sai của
biến phụ thuộc ≈ 0, và hồi quy không học được gì. **Bắt buộc mỗi miRNA chạy ≥ 2 thiết kế:**

| Nhóm | Chọn thế nào | n / miRNA |
|---|---|---|
| **A — top-1** | rank #1 theo V4 | 1 |
| **B — low-score** | candidate có `total_score` thấp nhất trong số vẫn qua hard-filter | 1 |
| **C — deliberate violation** (khuyến nghị, nếu ngân sách cho phép) | candidate cố ý vi phạm **đúng một** tiêu chí: Tm lệch > 5 °C, hoặc GC ngoài khoảng, hoặc có `CRITICAL` collider theo §1 | 1 |

Panel tối thiểu: **12 miRNA** × 2 thiết kế = 24 assay, phủ dải GC 30–70 % và độ dài 19–24 nt, gồm ít
nhất 2 cặp có `combined_risk == "CRITICAL"` từ §1.4 (ví dụ let-7a/let-7c, let-7a/let-7d) để test
trực tiếp trục đặc hiệu mới.

### 6.3 Biến phải đo (mỗi assay)

`efficiency_pct` (từ standard curve ≥ 5 điểm, dilution 10×, triplicate), `r_squared`, `slope`,
`cq_at_fixed_input`, `melt_tm_c`, `n_melt_peaks`, `ntc_cq`, `no_rt_cq`, `amplicon_verified`
(gel/sequencing, bool).

### 6.4 Schema intake

Tạo `calibration/wetlab_intake_schema.json` (JSON Schema draft-07) + template
`calibration/wetlab_results_template.csv` với đúng các cột trên, cộng `mirna_id`, `design_group`
(`A|B|C`), `predicted_score`, `predicted_grade`, `rt_worst_risk`, `combined_worst_risk`,
`replicate_id`, `operator`, `run_date`, `instrument`, `mastermix_lot`.

`calibration/calibrate_weights.py` (đã tồn tại) phải đọc được template này. **Không chạy calibration
cho tới khi có ≥ 20 assay hợp lệ** — giữ nguyên cổng D.3 đã có trong script, không được nới.

### 6.5 Tiêu chí chấp nhận dữ liệu (MIQE)

Loại assay khỏi tập fit nếu: `efficiency_pct` ngoài 80–120 %, `r_squared < 0.98`, `n_melt_peaks > 1`,
`ntc_cq - cq_at_fixed_input < 5`, hoặc `amplicon_verified == false`. Ghi lý do loại vào cột
`excluded_reason` — **không xoá hàng**.

### 6.6 Điều KHÔNG được làm

Không dùng dữ liệu wet-lab để "chỉnh" tới khi `success_rate = 100 %`. Mục đích của D.2 là tìm ca
thất bại; một calibration cho ra R² thấp nhưng trung thực có giá trị khoa học cao hơn một mô hình
overfit trên 24 điểm.

---

## 7. Định nghĩa hoàn thành

### 7.1 Gate cho từng commit

* `cd backend && pytest -q` — xanh toàn bộ.
* Không có `TODO`, `FIXME`, `PLACEHOLDER` mới trong code hoặc data file được commit.
* Mọi hằng số mới có comment nêu nguồn ([tag] + DOI/PMID) hoặc ghi rõ `heuristic, not experimentally
  anchored`.
* Không thêm dependency (kiểm bằng diff `backend/requirements.txt` và `frontend/package.json` —
  phải trống).

### 7.2 Gate hồi quy sau C2, C5, C12 (các commit đổi kết quả số)

```bash
cd backend && python app.py &
python validation/validate_primers.py --base-url http://localhost:5000
python validation/build_benchmark_validation.py --in-place
cd benchmark && python run_benchmark.py
```

* `checks_passed == checks_total` phải giữ nguyên. Nếu giảm → **dừng, báo cáo**, không sửa expected
  value để test xanh trở lại.
* Nếu `total_score` của bất kỳ target nào đổi > 5 điểm, ghi bảng before/after vào commit message.

### 7.3 Gate khoa học (tự kiểm, ghi kết quả vào PR description)

1. Chạy tool trên `hsa-let-7a-5p`. Panel mới **phải** liệt kê let-7c-5p ở mức `CRITICAL` và let-7b-5p
   ở mức `LOW`. Nếu ngược lại → hình học Kwok hoặc combined matrix sai.
2. Chạy trên `hsa-miR-503-5p`. Panel mới **phải** liệt kê ≥ 5 collider `rt_mismatch == 0` với
   `same_seed_family == False`; seed panel liệt kê **0** trong số đó.
3. Chạy trên `hsa-miR-21-5p`. `worst_combined_risk == "SAFE"`, `summary["CRITICAL"] == 0`.
4. Mở kết quả bất kỳ: không còn con số Tm điểm nào cho duplex < 8 nt trong UI hay export.
5. `python validation/build_benchmark_validation.py --check` → exit 0 trên repo sạch.

### 7.4 Không được làm trong SPEC này

* Không đổi `STEMLOOP_BODY`, `UNIVERSAL_REVERSE`, `OVERHANG_LENGTH_DEFAULT`.
* Không đổi trọng số trong `SCORING_WEIGHTS_V4` (chỉ đổi *nguồn* của một tiêu chí).
* Không xoá `cross_reactivity` khỏi API.
* Không chạy calibration wet-lab.
* Không thêm tính năng ngoài danh sách §0.2.

---

## 8. Tham chiếu

* **[Chen05]** Chen C et al. *Real-time quantification of microRNAs by stem-loop RT-PCR.*
  Nucleic Acids Res 2005;33(20):e179. — phương pháp gốc; overhang 6 nt.
* **[Kwok90]** Kwok S et al. *Effects of primer-template mismatches on the polymerase chain
  reaction.* Nucleic Acids Res 1990;18(4):999-1005. — trọng số vị trí mismatch tính từ **đầu 3′ của
  primer**.
* **[SL98]** SantaLucia J. PNAS 1998;95:1460-1465. — NN DNA:DNA.
* **[Sugimoto95]** Sugimoto N et al. Biochemistry 1995;34:11211-11216. — NN DNA:RNA hybrid.
* **[McTigue04]** McTigue PM et al. Biochemistry 2004;43:5388-5405. — NN LNA (single-LNA).
* **[Owczarzy11]** Owczarzy R et al. Biochemistry 2011;50:9352-9367. — LNA, gồm LNA liền kề.
* **[Ye12]** Ye J et al. BMC Bioinformatics 2012;13:134. — Primer-BLAST, tham số blastn-short.
* **[Wang17]** Wang Y et al. Mol Med Rep 2017;17(3):3690-3696. — phân biệt đơn nucleotide trong họ
  let-7.
* **[Neilsen12]** Neilsen CT, Goodall GJ, Bracken CP. Trends Genet 2012;28(11):544-549. — isomiR.
* **[MIQE09]** Bustin SA et al. Clin Chem 2009;55(4):611-622. — tiêu chí chấp nhận qPCR.
* **[K11]** Kramer MF. Curr Protoc Mol Biol 2011; Unit 15.10.

---

*Nguồn số liệu định lượng trong SPEC này (bucket 3′-6mer, ma trận let-7, danh sách collider của
miR-21/miR-503) được tính trực tiếp từ `backend/db/mirbase.db` (2 658 mature hsa) tại thời điểm
soạn spec. Nếu re-build miRBase làm đổi các con số này, cập nhật §1.4 kèm ghi chú release.*
