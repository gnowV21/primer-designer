/**
 * computeSeqAnalysis — tính toàn bộ thông tin cần thiết từ trình tự miRNA trưởng thành.
 * Trả về null nếu trình tự không hợp lệ.
 *
 * Các biến trả về được dùng để:
 *   - Hiển thị thông tin phân tích trong SequenceGroup (seed, GC, flags)
 *   - Cảnh báo kỹ thuật trong PrimerConstraintsGroup (repeat, fwdRegionGC, fwdEndGC)
 *   - Ghi chú sinh học trong DetectionMethodGroup (startsWithU)
 *   - Gửi lên backend khi thiết kế primer (bindingRegion, fwdRegion*)
 *
 * `bindingLen` = số nt ở đầu 3' mà overhang RT bám vào (tham số
 * `bindingRegion3prime`, 5-7 nt). KHÔNG mặc định cứng 6: người dùng đổi được,
 * và mọi chỉ số binding region bên dưới phải đi theo giá trị đó.
 */
import { DEFAULTS } from '../constants/defaults.js';

export function computeSeqAnalysis(
  matureSequence,
  bindingLen = DEFAULTS.primerConstraints.bindingRegion3prime,
) {
  const seq = (matureSequence || '').trim().toUpperCase();
  const isValid =
    seq.length >= 15 &&
    seq.length <= 30 &&
    /^[AUGC]+$/.test(seq);

  if (!isValid) return null;

  // --- Tính toán cơ bản ---
  const gcCount          = (seq.match(/[GC]/g) || []).length;
  const seedSeq          = seq.slice(1, 8);                       // nt 2–8
  const seedGcCount      = (seedSeq.match(/[GC]/g) || []).length;
  // Cửa sổ overhang: đọc từ bindingLen, kẹp vào [1, chiều dài trình tự].
  const bindingNt        = Math.max(
    1,
    Math.min(seq.length, Number(bindingLen) || DEFAULTS.primerConstraints.bindingRegion3prime),
  );
  const bindingSeq       = seq.slice(-bindingNt);                 // bindingNt nt cuối
  const bindingGcCount   = (bindingSeq.match(/[GC]/g) || []).length;
  const bindingAUcount   = bindingSeq.length - bindingGcCount;
  const fwdRegion        = seq.slice(0, Math.min(12, seq.length));
  const fwdGcCount       = (fwdRegion.match(/[GC]/g) || []).length;
  const fwdAUcount       = fwdRegion.length - fwdGcCount;

  return {
    // === Thông tin cơ bản ===
    length:     seq.length,
    gcContent:  parseFloat(((gcCount / seq.length) * 100).toFixed(1)),

    // Phân loại độ dài:
    //   'short' (15–17): có thể là fragment hoặc miRNA không điển hình
    //   'normal' (18–25): khoảng chuẩn của miRNA trưởng thành
    //   'long' (26–30): có thể là pre-miRNA fragment hoặc dạng không cắt hoàn chỉnh
    lengthCategory: seq.length < 18 ? 'short' : seq.length > 25 ? 'long' : 'normal',

    // === Seed region (nt 2–8 tính từ đầu 5') ===
    // Quyết định specificity và khả năng phân biệt các miRNA cùng họ
    seed7mer: seedSeq,
    seed6mer: seq.slice(1, 7),
    gcSeed:   parseFloat(((seedGcCount / seedSeq.length) * 100).toFixed(1)),

    // === Binding region (bindingNt nt cuối — RT primer bám vào đây) ===
    bindingRegion:        bindingSeq,
    bindingRegionLen:     bindingSeq.length,
    bindingRegionGcCount: bindingGcCount,
    bindingRegionGC:  parseFloat(((bindingGcCount / bindingSeq.length) * 100).toFixed(1)),
    // Tm ước tính theo Wallace rule: Tm = 2×(A+U) + 4×(G+C)
    // Chỉ dùng để ước tính nhanh độ bền của overhang RT primer (bindingNt nt).
    // Giá trị điển hình: 12°C (toàn AU) → 24°C (toàn GC).
    // Tm thực tế cao hơn do hairpin giữ primer ở vị trí, nhưng Tm thấp → phân biệt kém.
    bindingRegionTm: 2 * bindingAUcount + 4 * bindingGcCount,
    // 3+ nt giống nhau liên tiếp trong vùng binding — nghiêm trọng hơn so với
    // toàn trình tự vì đây là phần RT primer phải tổng hợp và bám chính xác
    bindingRegionHasRepeat: /([AUGC])\1{2,}/.test(bindingSeq),

    // === Forward primer specific region (12 nt đầu — phần đặc hiệu của fwd primer) ===
    fwdRegion10: seq.slice(0, 10),
    fwdRegion12: fwdRegion,
    fwdRegionGC: parseFloat(((fwdGcCount / fwdRegion.length) * 100).toFixed(1)),
    // Tm ước tính Wallace cho 12 nt đầu (chỉ phần specific, chưa tính đuôi 5′).
    // Để đạt tmMin ~58°C, đuôi 5′ cần bù phần còn thiếu: deficit = tmMin - fwdRegionTm.
    // Đuôi 10 nt tại ~50% GC đóng góp khoảng +30°C.
    fwdRegionTm: 2 * fwdAUcount + 4 * fwdGcCount,
    // GC clamp tại vị trí cuối của fwdRegion (≈ nt 12) — cần G/C để tránh 3' breathing
    fwdEndGC: /[GC]$/.test(fwdRegion),

    // === Đặc điểm đầu 5' ===
    startsWithU: seq[0] === 'U',   // canonical: Ago2 ưu tiên U ở vị trí 1
    end5prime:   seq.slice(0, 3),

    // === Đặc điểm đầu 3' ===
    end3prime:     seq.slice(-3),
    gcClamp3prime: /[GC]$/.test(seq),

    // === Flags cảnh báo toàn trình tự ===
    // ≥4 nt giống nhau liên tiếp bất kỳ chỗ nào → tổng hợp primer khó
    hasContinuousRepeat: /([AUGC])\1{3,}/.test(seq),
  };
}
