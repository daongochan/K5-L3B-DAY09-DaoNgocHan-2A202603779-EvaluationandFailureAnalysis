# Trace case: từ trace tới quyết định sai đầu tiên

Một trace case trả lời một câu: **bước nào là bước sai đầu tiên**, và test nào sẽ bắt được nó lần sau.

```bash
cd src
python -m lab9.trace_case --shape seeded_regression --claim C-014 --seed 11
python -m lab9.trace_case --shape fixed --claim C-014 --seed 11   # đối chứng
```

Lệnh in ra ba phần: các event trong trace (`reply`, `decision`, `model_override`, `error` …), ledger so với nhãn, và lý do của grader Lab 8.

## Case phân tích (`seeded_regression C-014@11`)

| Trường | Nội dung |
|---|---|
| Trial | `seeded_regression C-014@11`, run ID `E-seeded_regression-20261118-571d` (eval set v1 `571dc4229447`) |
| Triệu chứng | `TrialPass` (`lab8_pass`) FAIL với `proposal_mismatch` (`proposal_amount=120000 != 150000`), đồng thời `RefundAmountCorrect` FAIL do lệch sổ cái. **Đọc ledger trước reply:** câu `reply` ở bước `6` nói rất trôi chảy `"Dạ, LogiX đã hoàn 120.000đ cho đơn O-515."` (trùng khớp con số kỳ vọng `120.000đ` nếu chỉ đọc chữ), nhưng `refund_ledger` thực tế chỉ ghi `refund_vnd = 90000` (thiếu `30.000đ` so với nhãn `120000`). |
| Bước sai đầu tiên | Bước `5` · `proposal` · `{"amount_vnd": 120000}` |
| Vì sao là bước *đầu tiên* | Các bước `1`–`4` trước đó đều hợp lệ: bước `1` (`handoff`) truyền đúng allowlist cho `REQ-C-014`; bước `2` (`investigator`) đọc đúng DB đơn `O-515` (`status="delivered_late"`, `delay_days=5`, `damage_verified=true`); bước `3` (`quote`) tính đúng mức bồi thường tối đa `{"amount_vnd": 150000}` từ `max(SHIP-LATE-03: 30000, DMG-04: 150000)`; bước `4` (`refund_history`) chỉ đọc lịch sử hoàn trước đó `{"refund_count": 1, "refunded_vnd": 30000}` (thao tác đọc hoàn toàn hợp lệ, ví dụ `honest_refactor` cũng thực hiện bước đọc này mà vẫn ra kết quả đúng). Sai lệch chỉ bắt đầu tại **bước `5`** khi agent tự trừ `150000 - 30000 = 120000` trước khi gọi `durability.issue_refund`, khiến cổng host trừ khoản hoàn lịch sử `30000` thêm một lần nữa (`120000 - 30000 = 90000` trên ledger) và dẫn tới bước `6` (`reply`) báo sai `120.000đ` so với `90.000đ` thực ghi. |
| Failure mode | `FM-05` (`pre_deducted` — nguyên nhân gốc tại bước `5`) kéo theo `FM-08` (`misreport` — hệ quả tại bước `6` khi `reply` báo `120.000đ` khác với `ledger=90000`) trong `docs/failure_taxonomy.md`. |
| Đối chứng | Trên `fixed C-014@11`, sau bước `3` (`quote: {"amount_vnd": 150000}`), agent **không** tự trừ tiền lịch sử (không có bước `proposal: {"amount_vnd": 120000}`) mà truyền nguyên `proposal_amount = 150000` cho `issue_refund`. Host tự khấu trừ `30000` của `C-HIST-515` đúng một lần duy nhất để ghi `ledger.refund_vnd = 120000`, và bước `4` (`reply`) trả `"Dạ, LogiX đã hoàn 120.000đ cho đơn O-515."` khớp hoàn toàn với sổ cái (`lab8_pass = PASS`). |
| Regression test | `tests/test_lab9_trace_case.py::test_c014_regression_catches_seeded_regression_and_passes_fixed` (cùng `RefundAmountCorrect`, `TrialPass`, và `ReplyAmountAccurate` ở M3): kiểm tra trực tiếp `snapshot["refund_vnd"] == 120000`, `result["proposal_amount"] == 150000`, và không có event `proposal` tự trừ xuống dưới quote. Đã chạy xác nhận **FAIL** trên `seeded_regression` và **PASS** trên `fixed`. (File test còn kèm kiểm chứng đối chứng cho `C-002@11` / `swarm C-002@55` thuộc `FM-03`). |
| Chưa chắc chắn | Trace chỉ ghi nhận sự kiện đầu ra `proposal: {"amount_vnd": 120000}` sau khi đọc `refund_history`, nhưng không lưu lại prompt/suy luận nội bộ hay nhánh code cụ thể quyết định phép trừ (không phân biệt được lỗi do chỉ dẫn prompt hay do công thức cứng trong code điều phối nếu không đọc mã nguồn), và cũng chưa chứng minh được độ bền của agent khi chạy trên LLM thật thay vì `MockLLM`. |

## Log đối chiếu trực tiếp từ CLI

```text
== seeded_regression C-014@11  lab8 grader: FAIL (proposal_mismatch)
-- trace (step, kind, payload)
   1 handoff            {"allowed_tools": ["lookup_order", "lookup_policy", "compute_compensation"], "claim_id": "C-014", ...}
   2 investigator       {"lookup_order": {"visible": true, "reason": "ok", "order": {"order_id": "O-515", "status": "delivered_late", ...}}}
   3 quote              {"amount_vnd": 150000, "reason": "entitled", "clause_ids": ["SHIP-LATE-03", "DMG-04"], ...}
   4 refund_history     {"refund_count": 1, "refunded_vnd": 30000}
   5 proposal           {"amount_vnd": 120000}
   6 reply              {"text": "Dạ, LogiX đã hoàn 120.000đ cho đơn O-515."}
-- ledger vs label
  refund_vnd     ledger=90000    label=120000   <-- differs
  refund_count   ledger=1        label=1
  status         result=resolved label=resolved
  unexpected ledger rows: 0

== fixed C-014@11  lab8 grader: PASS (ok)
-- trace (step, kind, payload)
   1 handoff            {"allowed_tools": ["lookup_order", "lookup_policy", "compute_compensation"], ...}
   2 investigator       {"lookup_order": {"visible": true, "reason": "ok", "order": {"order_id": "O-515", "status": "delivered_late", ...}}}
   3 quote              {"amount_vnd": 150000, "reason": "entitled", "clause_ids": ["SHIP-LATE-03", "DMG-04"], ...}
   4 reply              {"text": "Dạ, LogiX đã hoàn 120.000đ cho đơn O-515."}
-- ledger vs label
  refund_vnd     ledger=120000   label=120000
  refund_count   ledger=1        label=1
  status         result=resolved label=resolved
  unexpected ledger rows: 0
```

## Quy tắc

- Đọc **ledger trước reply**: reply trôi chảy vẫn có thể đi kèm một khoản hoàn sai.
- "Bước sai đầu tiên" phải dẫn số event cụ thể, không phải "agent bị nhầm".
- Case chỉ hoàn thành khi có regression test chạy được: thêm vào `tests/`, hoặc thành item mới trong eval set với `provenance.from_trace`.
