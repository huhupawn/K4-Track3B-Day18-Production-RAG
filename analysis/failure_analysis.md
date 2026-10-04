# Failure Analysis — Lab 18: Production RAG

**Họ và tên học viên:** Nguyen Anh Hoang  
**Khóa:** K4 - Track 3B

---

## RAGAS Scores

| Metric            | Naive Baseline | Production | Δ       |
| ----------------- | -------------- | ---------- | ------- |
| Faithfulness      |                |            |         |
| Answer Relevancy  |                |            |         |
| Context Precision |                |            |         |
| Context Recall    |                |            |         |
| Faithfulness      | 1.0000         | 1.0000     | +0.0000 |
| Answer Relevancy  | 0.5605         | 0.6437     | +0.0832 |
| Context Precision | 0.8875         | 0.9917     | +0.1042 |
| Context Recall    | 0.7193         | 0.7444     | +0.0251 |

---

## Bottom-5 Failures

### #1

- **Question:**
- **Expected:**
- **Got:**
- **Worst metric:**
- **Error Tree:** Output sai → Context đúng? → Query OK? →
- **Root cause:**
- **Suggested fix:**
- **Question:** Bao lâu phải đổi mật khẩu một lần?
- **Expected:** Theo chính sách hiện hành (v2.0), mật khẩu phải được thay đổi mỗi 120 ngày. Chính sách cũ yêu cầu 90 ngày nhưng đã bị thay thế.
- **Got:** Trích từ mat_khau_v1.md. Không được sử dụng tên đăng nhập hoặc các thông tin cá nhân dễ đoán làm mật khẩu. ## Chu kỳ thay đổi Mật khẩu phải được thay đổi **mỗi 90 ngày**. Hệ thống sẽ tự động nhắc nhở trước 7 ngày. Mật khẩu mới không được trùng với 3 mật khẩu gần nhất.
- **Worst metric:** Context Recall (0.4286)
- **Error Tree:** Output sai (chọn 90 ngày thay vì 120 ngày) → Context cũ được ưu tiên hơn context mới → Retrieval thiếu bộ lọc phiên bản tài liệu.
- **Root cause:** Knowledge base có cả văn bản chính sách cũ (`mat_khau_v1.md`) và văn bản chính sách mới (`mat_khau_v2.md`). Do mật độ từ khóa tương đồng, pipeline chưa có cơ chế metadata filtering theo version hoặc status để loại bỏ tài liệu đã hết hiệu lực.
- **Suggested fix:** Áp dụng Metadata Filtering (M5/M2) dựa trên trường `doc_version` hoặc `status: active`/`is_deprecated`, chỉ index hoặc ưu tiên tìm kiếm các văn bản đang có hiệu lực thi hành.

### #2

(copy template)

- **Question:** Một nhân viên Senior có 9 năm thâm niên được nghỉ bao nhiêu ngày phép năm và lương trong khoảng nào?
- **Expected:** Theo chính sách v2024: 15 ngày cơ bản + 3 ngày thâm niên (9÷3=3) = 18 ngày phép. Lương Senior (P3-P4): 20-35 triệu VNĐ/tháng.
- **Got:** Trích từ nghi_phep_nam_v2024.md. Ví dụ: nhân viên 9 năm thâm niên được 18 ngày phép (15 + 3). ## Quy định sử dụng Phép năm phải được đăng ký trước ít nhất 2 ngày làm việc qua hệ thống HR Portal.
- **Worst metric:** Context Recall (0.3810)
- **Error Tree:** Output chỉ trả lời được 1 vế (ngày phép), thiếu vế thứ 2 (mức lương) → Context thiếu hoàn toàn tài liệu thang bảng lương → Retrieval đơn truy vấn không thể bao quát 2 chủ đề độc lập.
- **Root cause:** Câu hỏi thuộc dạng Multi-hop reasoning và đa thực thể (nghỉ phép thâm niên + thang bảng lương Senior). Đơn truy vấn bị bias theo chủ đề có nhiều từ khóa hơn (phép năm), khiến các chunk về lương không lọt vào top-k.
- **Suggested fix:** Cài đặt Sub-query Decomposition (Query Routing) để tách câu hỏi gốc thành 2 câu hỏi con độc lập: (1) "Thâm niên 9 năm được bao nhiêu ngày phép năm?" và (2) "Mức lương nhân viên bậc Senior là bao nhiêu?", sau đó hợp nhất contexts trước khi rerank.

### #3

(copy template)

- **Question:** Nếu cần mua một chiếc laptop 30 triệu cho nhân viên mới, ai phê duyệt và cần gì từ phòng CNTT?
- **Expected:** Laptop 30 triệu nằm trong khoảng 5-50 triệu nên cần Giám đốc phòng ban (Director) phê duyệt. Ngoài ra, mua sắm thiết bị CNTT cần có xác nhận cấu hình kỹ thuật từ phòng CNTT trước khi đề xuất. Cần đính kèm ít nhất 3 báo giá vì trên 10 triệu.
- **Got:** Trích từ mua_sam.md. Mua sắm thiết bị CNTT (laptop, server, phần mềm) cần có xác nhận của phòng CNTT về cấu hình kỹ thuật trước khi đề xuất. Đơn hàng khẩn cấp có thể bỏ qua yêu cầu 3 báo giá nhưng phải có giải trình bằng văn bản.
- **Worst metric:** Answer Relevancy (0.3333)
- **Error Tree:** Output trả lời đúng thủ tục CNTT nhưng thiếu thẩm quyền phê duyệt ngân sách → Context lấy đúng chunk quy trình CNTT nhưng trượt chunk bảng phân cấp hạn mức duyệt ngân sách → Chunking phân mảnh thông tin bảng biểu.
- **Root cause:** Trong tài liệu `mua_sam.md`, quy định về cấu hình CNTT nằm ở mục riêng, còn bảng hạn mức số tiền (5 - 50 triệu thuộc thẩm quyền Director) nằm ở mục bảng ma trận thẩm quyền. Khi chunk kích thước nhỏ được rank theo từ khóa "laptop", chunk chứa bảng hạn mức bị điểm thấp hơn.
- **Suggested fix:** Áp dụng Hierarchical Chunking (Parent-Child) với Parent chunk chứa toàn bộ bối cảnh bảng hạn mức thẩm quyền, hoặc sử dụng Multi-vector Retrieval với Document Summary.

### #4

(copy template)

- **Question:** Nhân viên tạm ứng 15 triệu, sau 20 ngày mới thanh toán. Bị phạt bao nhiêu?
- **Expected:** Thời hạn thanh toán là 15 ngày. Quá hạn 5 ngày, bị tính phí 2%/tháng trên 15.000.000 VNĐ = 300.000 VNĐ/tháng (tính pro-rata khoảng 50.000 VNĐ cho 5 ngày).
- **Got:** Trích từ bao_hiem_suc_khoe.md. Trường hợp khám ngoài danh sách, nhân viên thanh toán trước và nộp hồ sơ bồi hoàn trong vòng 30 ngày. Thời gian xử lý bồi hoàn: 10-15 ngày làm việc.
- **Worst metric:** Answer Relevancy (0.3750)
- **Error Tree:** Output trích nhầm tài liệu bảo hiểm sức khỏe → Context trích sai hoàn toàn tài liệu tạm ứng công tác → Dense retrieval bị đánh lừa bởi từ "thanh toán", "ngày".
- **Root cause:** Từ khóa "tạm ứng", "phạt" bị nhiễu ngữ nghĩa bởi cụm từ "thanh toán trước", "ngày làm việc" xuất hiện lặp lại trong quy trình bồi hoàn bảo hiểm y tế.
- **Suggested fix:** Triển khai HyDE (Hypothetical Document Embeddings) để giả lập câu trả lời chứa quy định tạm ứng tài chính trước khi embed, kết hợp tăng trọng số BM25 cho thuật ngữ chuyên ngành "tạm ứng hoàn ứng".

### #5

(copy template)

- **Question:** Muốn mua thiết bị trị giá 55 triệu cần ai phê duyệt?
- **Expected:** Đơn hàng trên 50.000.000 VNĐ cần Tổng Giám đốc (CEO) phê duyệt.
- **Got:** Trích từ nghi_phep_khong_luong.md. Nghỉ từ 1-5 ngày: trưởng phòng phê duyệt. Nghỉ từ 6-15 ngày: cần thêm phê duyệt của Giám đốc Nhân sự. Nghỉ từ 16-30 ngày: cần phê duyệt của Giám đốc điều hành (CEO).
- **Worst metric:** Answer Relevancy (0.2500)
- **Error Tree:** Output chọn nhầm quy trình phê duyệt nghỉ phép → Context lấy nhầm sang `nghi_phep_khong_luong.md` vì cùng chứa "cần ai phê duyệt" và "CEO" → Retrieval bị semantic similarity đánh lừa.
- **Root cause:** Câu hỏi có cấu trúc "cần ai phê duyệt" tương đồng ngữ nghĩa cao với thẩm quyền duyệt nghỉ phép cấp cao của CEO, trong khi con số "55 triệu" đòi hỏi suy luận logic so sánh ngưỡng (> 50 triệu) thay vì match nguyên văn chuỗi "55 triệu".
- **Suggested fix:** Trích xuất Metadata số học và thực thể (Named Entity Recognition: tiền tệ, thiết bị), kết hợp BM25 ưu tiên các chunk có keyword `mua sắm`, `thiết bị` thay vì chỉ dựa vào embedding ngữ nghĩa câu hỏi.

---

## Case Study (cho presentation)

**Question chọn phân tích:**

> _"Bao lâu phải đổi mật khẩu một lần?"_

**Error Tree walkthrough:**

1. Output đúng? →
2. Context đúng? →
3. Query rewrite OK? →
4. Fix ở bước:
5. **Output đúng?** → **KHÔNG**. Output trả lời "mỗi 90 ngày" dựa trên chính sách `mat_khau_v1.md`, trong khi thực tế quy định hiện hành `mat_khau_v2.md` là "mỗi 120 ngày".
6. **Context đúng?** → **KHÔNG**. Chunk được rank cao nhất thuộc về file cũ đã hết hiệu lực do từ khóa BM25 và độ tương đồng ngữ nghĩa của câu "Mật khẩu phải được thay đổi mỗi 90 ngày" match gần như hoàn hảo với câu hỏi.
7. **Query rewrite OK?** → Câu hỏi nguyên bản quá ngắn gọn, không có ngữ cảnh về "thời điểm hiện tại" hoặc "chính sách mới nhất", khiến retrieval không thể phân biệt giữa v1 và v2.
8. **Fix ở bước:**
   - **Bước 1 (Metadata Extraction & Filtering):** Khi ingest tài liệu ở M5, gán metadata `status: deprecated` cho `mat_khau_v1.md` và `status: active` cho `mat_khau_v2.md`. Tại M2, filter `status == 'active'` trước khi search.
   - **Bước 2 (Query Transformation):** Bổ sung Query Rewriting để tự động mở rộng "theo quy định hiện hành mới nhất".

## **Nếu có thêm 1 giờ, sẽ optimize:**

- **Thêm tính năng Temporal / Version Filtering:** Tự động phát hiện phiên bản tài liệu (`v1`, `v2`, ngày hiệu lực) để loại bỏ hoàn toàn các tài liệu cũ đã bị thay thế khỏi search space mặc định.
- **Triển khai Query Decomposition Agent:** Xử lý các câu hỏi multi-hop (như câu thâm niên 9 năm + lương Senior) thành các sub-queries song song để đạt context recall 100%.
