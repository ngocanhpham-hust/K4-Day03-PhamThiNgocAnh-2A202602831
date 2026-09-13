# 📊 BÁO CÁO THU HOẠCH NGHIỆM THU BÀI LAB 3 (BƯỚC 3 — SUBMISSION ARTIFACT)

> **Họ và Tên Học viên:** Phạm Thị Ngọc Anh
>
> **Mã Sinh Viên / Mã Học viên:** 2A202602831
>
> **Chủ đề Lựa chọn:** Trợ lý Học vụ & Tra cứu Lịch thi VinUni

---

## 1. BẢNG CHẤM ĐIỂM AGENTIC FIT SCORING MATRIX (ĐÁNH GIÁ CHỦ ĐỀ)

| Tiêu chí Đánh giá | Mức độ (1 - 5) | Giải trình chi tiết lý do chọn điểm |
| :--- | :---: | :--- |
| **1. Multi-step Reasoning** | 5 / 5 | Yêu cầu đặt lịch cần phân tích thông tin còn thiếu, tra cứu hồ sơ để xác định cố vấn, sau đó mới thực hiện đặt lịch và tổng hợp kết quả. |
| **2. Tool Interaction** | 5 / 5 | Agent sử dụng ba tool qua MCP Server để đọc điểm, đọc lịch thi và ghi lịch hẹn vào các nguồn dữ liệu JSON độc lập. |
| **3. Dynamic Decision** | 5 / 5 | Tool tiếp theo phụ thuộc vào intent và Observation: có thể trả lời trực tiếp, hỏi lại, tra cứu một tool hoặc tiếp tục chuỗi tra cứu → đặt lịch. |
| **4. Long Horizon Goal** | 3 / 5 | Agent duy trì mục tiêu trong tối đa 5 vòng ReAct của một phiên; bài demo chưa có bộ nhớ dài hạn giữa nhiều phiên hội thoại. |
| **TỔNG ĐIỂM AGENTIC FIT** | **18 / 20** | *Tổng điểm > 12/20: Bài toán rất phù hợp triển khai Agentic System.* |

---

## 2. TRÍCH XUẤT KẾT QUẢ WATERFALL TRACE LOG (SAU KHI CHẠY TEST SUITE TRÊN API THẬT)

> ⚠️ **YÊU CẦU NGHIỆM THU:** Mở tệp `.env` điền `GEMINI_API_KEY` (hoặc `OPENAI_API_KEY`) để kết nối LLM thật trước khi thực thi `python src/app.py --all`. Bài nộp chỉ dùng Mock Offline Provider sẽ không đạt điểm nghiệm thực tế.

Dưới đây là đoạn trích thu gọn từ lượt Gemini gọi `exam_schedule_query`. Bản ghi đầy đủ
(gồm cả 3 môn thi và Final Answer) nằm trong `docs/trace_waterfall.json`:

```json
[
  {
    "run_id": "b3250c42e1",
    "timestamp": "2026-09-13T16:11:01+07:00",
    "step": 1,
    "query": "Cho tôi xem lịch thi của sinh viên SV2026001.",
    "action_type": "TOOL_EXECUTION",
    "llm_provider": "GeminiProvider",
    "llm_source": "GeminiProvider",
    "thought": "Gemini quyết định gọi công cụ 'exam_schedule_query' với tham số student_id SV2026001",
    "tool_name": "exam_schedule_query",
    "arguments": {"student_id": "SV2026001"},
    "observation": {
      "status": "SUCCESS",
      "student_id": "SV2026001",
      "total_exams": 3,
      "exams": [
        {
          "course_name": "Cấu trúc dữ liệu và giải thuật",
          "course_code": "COMP1020",
          "exam_room": "C401",
          "exam_datetime": "08:00 28/09/2026",
          "exam_class_code": "COMP1020-E01",
          "exam_format": "Trắc nghiệm và tự luận trên giấy",
          "exam_content": "40 câu trắc nghiệm và 2 câu tự luận trong 90 phút"
        }
      ]
    },
    "latency_ms": 2939.25
  }
]
```

**Ghi chú quan sát:** Trace hiện có 20 sự kiện, trong đó 15 sự kiện được phản hồi trực
tiếp bởi `GeminiProvider`. Một số lượt cuối chạm giới hạn quota miễn phí và được đánh
dấu minh bạch là `mock_fallback`; hệ thống không ghi nhận nhầm các lượt này là API thật.

---

## 3. TỔNG KẾT KẾT QUẢ NGHIỆM THU & NỘP BÀI

- [x] Đã điền API Key thật trong `.env` và xác nhận Native Tool Calling hoạt động với Gemini.
- **Tổng số Test Cases đã chạy thành công:** 5 / 5 test cases.
- **Số lượt gọi Tool qua MCP Server chính xác:** 6 lượt trong bộ 5 test; 11 lượt trong artifact trace sau khi chạy thêm demo lịch thi và kiểm tra đa bước.
- **Kết quả đẩy Repo nộp bài:** [ ] Đã Commit và Push mã nguồn thành công lên GitHub cá nhân.

### Product Demo bổ sung

- Streamlit UI tiếng Việt gồm: Trợ lý AI, GPA & CPA, Lịch thi, Lịch tư vấn và Trace Lab.
- So sánh trực tiếp Chatbot Baseline với ReAct Agent + MCP trên cùng một câu hỏi.
- Dữ liệu mock tách thành JSON; lịch hẹn mới được lưu bền vững vào `data/appointments.json`.
- Trace UI hiển thị Decision Summary, Action, Arguments, Observation, Final Answer và latency; hỗ trợ tải file JSON.

---

> ✅ **HOÀN TẤT NỘP BÀI:** Sao chép đường link GitHub Repository cá nhân của bạn và dán vào ô nộp bài trên hệ thống LMS VLearn để hoàn tất Bài Lab 3!
