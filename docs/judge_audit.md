# Judge audit

Chạy kiểm định:
```bash
cd src
python -m lab9.judge --csv data/eval/judge_tone_public.csv --audit 10
python -m lab9.judge --csv data/eval/judge_helpful_public.csv --audit 10
```

## Tổng hợp hiệu chuẩn (Calibration Summary — lớp dương tính: `FAIL`)

| Tiêu chí | n | Confusion (`tp / fp / fn / tn`) | κ | Precision | Recall | Fail rate (Obs → Rogan-Gladen) | Đạt FLOORS (`κ≥0.6`, `P≥0.8`, `R≥0.7`)? | Quyết định |
|---|---|---|---|---|---|---|---|---|
| `tone_ok` | 100 | `24 / 4 / 6 / 66` | `0.757` | `0.857` | `0.800` | `0.280 → 0.300` | **Có** (`PASS floors`) | **Dùng** (cho đánh giá giọng điệu, kèm cập nhật rubric dưới đây) |
| `helpful` | 100 | `9 / 0 / 21 / 70` | `0.375` | `1.000` | `0.300` | `0.090 → 0.300` | **Không** (`FAIL floors`: `κ=0.375<0.6`, `R=0.300<0.7`) | **Loại** (cấm dùng làm gate) |

---

## Audit thủ công các ca bất đồng (`tone_ok` & `helpful`)

| # | Case | Nội dung `reply` (trích) | Judge nói | Người nói | Ai đúng? | Phân tích lỗi & Hành động sửa rubric / bộ nhãn |
|---|---|---|---|---|---|---|
| 1 | `H-008` (`tone_ok`) | `"Em đã hoàn tiền cho anh rồi nha, anh check giúp em."` | `PASS` | `FAIL` | **Người đúng** (`FN`) | Xưng `"em"` + trợ từ `"nha"` quá suồng sã; judge nhầm là thân thiện. **Sửa rubric:** quy định cứng cặp xưng hô chuẩn `"LogiX"` – `"anh/chị"`, đánh `FAIL` mọi câu xưng `"em"`, `"bạn"`, `"mình"` hoặc dùng từ khẩu ngữ `"nha"`, `"nhé"`. |
| 2 | `H-017` (`tone_ok`) | `"Dạ, bạn ơi LogiX đã hoàn 25.000đ cho đơn O-606 rồi nha."` | `PASS` | `FAIL` | **Người đúng** (`FN`) | Mặc dù có `"Dạ"`, việc gọi khách là `"bạn ơi"` kèm `"rồi nha"` vi phạm chuẩn CSKH với khách lớn tuổi. **Sửa rubric:** bổ sung few-shot phản ví dụ có từ `"Dạ"` nhưng sai đại từ (`"bạn ơi"` → `FAIL`). |
| 3 | `H-029` (`tone_ok`) | `"Dạ, vui lòng chờ. Hệ thống đang xử lý, không cần nhắn thêm."` | `PASS` | `FAIL` | **Người đúng** (`FN`) | Vế sau mang giọng ra lệnh, chặn họng khách (`"không cần nhắn thêm"`); judge bị đánh lừa bởi cụm mở đầu lịch sự `"Dạ, vui lòng"`. **Sửa rubric:** yêu cầu xét toàn bộ câu; cấm các mệnh lệnh phủ định đuổi khách (`"không cần nhắn thêm"`, `"khỏi hỏi nữa"`). |
| 4 | `H-042` (`tone_ok`) | `"Dạ, đơn O-808 đã hoàn 120.000đ. Tiền về trong 3–5 ngày ạ."` | `FAIL` | `PASS` | **Người đúng** (`FP`) | Câu ngắn gọn, đủ kính ngữ `"Dạ ... ạ"` và đủ thông tin thời gian nhận tiền; judge phạt oan vì thiếu câu xin lỗi. **Sửa rubric:** ghi rõ không bắt buộc câu xin lỗi mẫu khi thông báo kết quả hoàn tiền thành công, tránh thiên kiến ưa câu dài (verbosity bias). |
| 5 | `H-051` (`tone_ok`) | `"Dạ, LogiX đã refund 90.000đ cho đơn O-202 ạ."` | `FAIL` | `PASS` | **Người đúng** (`FP`) | CSKH LogiX cho phép dùng thuật ngữ `"refund"`; judge phạt máy móc vì pha tiếng Anh. **Sửa rubric:** thêm danh sách từ mượn nghiệp vụ được phép (`refund`, `order`, `ship`, `voucher`) khi đi kèm câu tiếng Việt lịch sự. |
| 6 | `H-063` (`tone_ok`) | `"Dạ, LogiX đã hoàn 20.000đ và sẽ hoàn thêm cho anh/chị ạ."` | `PASS` | `FAIL` | **Người đúng** (`FN`) | Tự ý hứa hẹn `"sẽ hoàn thêm"` vượt thẩm quyền hệ thống. **Sửa rubric & kiến trúc:** bổ sung điều khoản cấm cam kết bồi thường ngoài kết quả đã chốt vào rubric CSKH, đồng thời tách kiểm tra cam kết tiền tệ sang grader chuyên biệt. |
| 7 | `H-070` (`tone_ok`) | `"Dạ, LogiX đã hoàn 90.000đ cho đơn O-909 ạ 😂😂"` | `PASS` | `FAIL` | **Người đúng** (`FN`) | Dùng emoji cười cợt `😂😂` phản cảm trong bối cảnh giải quyết khiếu nại. **Sửa rubric (hoặc tiền lọc regex):** cấm sử dụng emoji biểu cảm đùa cợt trong phản hồi khiếu nại. |
| 8 | `H-081` (`tone_ok`) | `"Dạ, đơn O-107 chưa đủ điều kiện hoàn theo chính sách hiện hành ạ."` | `FAIL` | `PASS` | **Judge đúng** (`FP` giả) | Người gán nhãn đọc nhầm ticket nên gán sai nhãn `PASS` (câu từ chối cộc lốc, thiếu lời mời hỗ trợ tiếp theo theo chuẩn mẫu từ chối của LogiX). **Hành động:** **sửa nhãn chuẩn (`human` → `FAIL`)** trong bộ dữ liệu đối chuẩn và yêu cầu quy trình gán nhãn kép (2 annotator) cho bộ held-out. |
| 9 | `H-088` (`tone_ok`) | `"Dạ, dạ, LogiX đã hoàn 40.000đ cho đơn O-233 ạ."` | `FAIL` | `PASS` | **Người đúng** (`FP`) | Lặp chữ `"Dạ, dạ"` nhẹ do lỗi gõ/sinh từ nhưng thái độ vẫn lịch sự; judge phạt quá nặng lỗi hình thức. **Sửa rubric:** phân biệt lỗi lặp từ nhẹ không gây phản cảm (`PASS` về tone) với lỗi mất lịch sự (`FAIL`). |
| 10 | `H-094` (`tone_ok`) | `"Da, LogiX da hoan 40.000đ cho don O-341, xin loi vi su bat tien."` | `PASS` | `FAIL` | **Người đúng** (`FN`) | Văn bản mất toàn bộ dấu tiếng Việt (kiểu dịch máy/lỗi encoding), thiếu chuyên nghiệp. **Sửa rubric (kèm rule code):** bắt buộc phản hồi tiếng Việt có dấu chuẩn xác. |
| 11 | `HL-016` (`helpful`) | `"Dạ, LogiX thành thật xin lỗi anh/chị... LogiX đã hoàn 55.000đ cho đơn O-404..."` *(ledger ghi 35.000đ)* | `PASS` | `FAIL` | **Người đúng** (`FN`) | Báo sai số tiền (`55.000đ` so với ledger `35.000đ` — `FM-08`), nhưng viết lời xin lỗi cực kỳ dài và thống thiết nên judge bị **verbosity/politeness bias** đánh lừa. **Hành động:** loại bỏ judge `helpful`; chuyển kiểm tra khớp số tiền `reply` – `ledger` sang **code grader** (`ReplyAmountAccurate`). |
| 12 | `HL-047` (`helpful`) | `"Ok bạn, đơn O-515 xử lý rồi nhé."` | `PASS` | `FAIL` | **Người đúng** (`FN`) | Vừa sai xưng hô (`"Ok bạn ... nhé"`), vừa thiếu thông tin số tiền/kết quả cụ thể do tiêu chí `"helpful"` quá chung chung. **Hành động:** tách tiêu chí gộp `"helpful"` thành `tone_ok` (judge đã calibrate) + kiểm tra trạng thái/số tiền bằng code. |

---

## Kết luận

1. **Tiêu chí bị loại (`helpful`) và lý do không được dùng làm CI gate:**
   - **Bằng chứng định lượng từ ma trận nhầm lẫn (`tp=9, fp=0, fn=21, tn=70`):** Trong 30 ca lỗi thực tế (`tp + fn = 30`), judge `helpful` chỉ bắt được 9 ca và **bỏ lọt tới 21 ca (`fn = 21`)**, khiến **Recall chỉ đạt `0.300`** (thấp xa ngưỡng sàn `0.7`) và **Cohen's $\kappa = 0.375$** (thấp xa ngưỡng sàn `0.6`). Tỉ lệ lỗi quan sát được của judge chỉ là `9.0%`, đánh giá thấp hơn **3.3 lần** so với tỉ lệ lỗi thực sau hiệu chỉnh Rogan-Gladen (`30.0%`).
   - **Nguyên nhân gốc rễ:** Trong 21 ca bỏ lọt (`fn`), có tới **18 ca là lỗi báo sai số tiền so với sổ cái (`FM-08`)** và 3 ca sai xưng hô. Do tiêu chí `"helpful"` gộp chung nhiều chiều (thái độ + độ đầy đủ + độ chính xác nghiệp vụ), LLM judge không nhìn thấy dữ liệu thật trong `refund_ledger` và bị **thiên kiến ưa lời văn dài dòng, lịch sự (verbosity/sycophancy bias)** — cứ thấy xin lỗi tha thiết là chấm `PASS` bất chấp con số hoàn tiền bịa đặt. Nếu đưa `helpful` làm cổng chặn release, các bản lỗi nghiêm trọng về tiền tệ (`FM-08`) sẽ lọt qua CI gate hoàn toàn.
   - **Giải pháp thay thế:** Loại bỏ hoàn toàn judge `helpful`. Áp dụng nguyên tắc *"tiền và phê duyệt luôn chấm bằng code"*: dùng code grader `ReplyAmountAccurate` (M3) đối chiếu trực tiếp số tiền trong `reply` với `snapshot["refund_vnd"]`, và chỉ dùng LLM judge riêng cho chiều giọng điệu `tone_ok` (đã đạt $\kappa = 0.757 \ge 0.6$, $P = 0.857 \ge 0.8$, $R = 0.800 \ge 0.7$).

2. **Rủi ro còn lại:**
   - Kết quả hiệu chuẩn hiện tại chỉ đo từ dữ liệu replay đã công khai (`n = 100` mẫu cho mỗi judge).
   - Mọi chỉnh sửa trên rubric `tone_ok` rút ra từ việc đọc 10 ca bất đồng của tập public đều có nguy cơ overfit vào chính tập này; trước khi đưa judge đã sửa rubric vào vận hành thật, bắt buộc phải thu thập và gán nhãn kép một **tập held-out mới hoàn toàn độc lập** để hiệu chuẩn lại.
