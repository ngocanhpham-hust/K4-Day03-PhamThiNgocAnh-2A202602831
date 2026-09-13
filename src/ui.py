"""Giao diện Streamlit cho demo Trợ lý Học vụ VinUni."""

import json
import os
import sys
from datetime import date, datetime, time, timedelta

import streamlit as st

SRC_DIR = os.path.dirname(os.path.abspath(__file__))
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from app import get_final_answer, run_baseline_chatbot, run_react_agent, save_waterfall_trace
from mcp_server import MCPAcademicServer
from providers import get_llm_provider
from tools import APPOINTMENTS_PATH, EXAMS_PATH, STUDENTS_PATH, _read_json


st.set_page_config(
    page_title="VinUni Academic Copilot",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    .stApp { background: #f6f8fb; }
    [data-testid="stSidebar"] { background: #14213d; }
    [data-testid="stSidebar"] * { color: #f8fafc; }
    .hero {
        padding: 1.5rem 1.7rem; border-radius: 18px;
        background: linear-gradient(120deg, #8b1538 0%, #b4234d 55%, #e09f3e 100%);
        color: white; margin-bottom: 1rem;
        box-shadow: 0 10px 28px rgba(139, 21, 56, .18);
    }
    .hero h1 { margin: 0; font-size: 2rem; }
    .hero p { margin: .45rem 0 0; opacity: .92; }
    .trace-card {
        border-left: 4px solid #8b1538; background: white; padding: .85rem 1rem;
        border-radius: 8px; margin: .55rem 0; box-shadow: 0 2px 8px rgba(15,23,42,.06);
    }
    .small-muted { color: #64748b; font-size: .86rem; }
    div[data-testid="stMetric"] { background: white; border: 1px solid #e2e8f0; padding: .8rem; border-radius: 12px; }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_resource
def services():
    return get_llm_provider(), MCPAcademicServer()


def load_trace():
    path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "docs", "trace_waterfall.json")
    try:
        with open(path, "r", encoding="utf-8") as file:
            content = json.load(file)
            return content if isinstance(content, list) else []
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def render_trace(events):
    if not events:
        st.info("Chưa có trace. Hãy gửi một yêu cầu cho Agent hoặc chạy test suite.")
        return
    for event in events:
        is_tool = event.get("action_type") == "TOOL_EXECUTION"
        title = (
            f"🛠️ Bước {event.get('step')} · {event.get('tool_name', 'Tool')}"
            if is_tool else f"🏁 Bước {event.get('step')} · Final Answer"
        )
        st.markdown(
            f'<div class="trace-card"><strong>{title}</strong><br>'
            f'<span class="small-muted">{event.get("latency_ms", 0)} ms · '
            f'{event.get("timestamp", "Không có timestamp")}</span></div>',
            unsafe_allow_html=True,
        )
        with st.expander("Chi tiết Thought → Action → Observation", expanded=False):
            st.write("**Thought (decision summary):**", event.get("thought", "—"))
            if is_tool:
                st.write("**Action:**", event.get("tool_name"))
                st.json(event.get("arguments", {}))
                st.write("**Observation:**")
                st.json(event.get("observation", {}))
            else:
                st.write("**Kết quả:**", event.get("output", ""))


provider, mcp_server = services()
students = _read_json(STUDENTS_PATH, {})
exams = _read_json(EXAMS_PATH, {})

with st.sidebar:
    st.markdown("## 🎓 Academic Copilot")
    st.caption("Trợ lý Học vụ & Tra cứu Lịch thi")
    st.divider()
    st.write("**Chế độ LLM**")
    provider_name = provider.__class__.__name__
    if provider_name == "MockOfflineProvider":
        st.warning("Mock Offline")
        st.caption("Thêm GEMINI_API_KEY vào .env để nghiệm thu bằng API thật.")
    else:
        st.success(provider_name)
    st.write("**MCP Server**")
    st.success(f"Online · {len(mcp_server.list_tools())} tools")
    st.divider()
    st.caption("Dữ liệu demo: SV2026001, SV2026002")

st.markdown(
    """
    <div class="hero">
      <h1>VinUni Academic Copilot</h1>
      <p>Tra cứu kết quả học tập, lịch thi và đặt lịch với cố vấn — có thể quan sát từng bước ReAct.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

tab_agent, tab_gpa, tab_exam, tab_booking, tab_trace = st.tabs(
    ["🤖 Trợ lý AI", "📊 GPA & CPA", "🗓️ Lịch thi", "🤝 Lịch tư vấn", "🔎 Trace Lab"]
)

with tab_agent:
    st.subheader("Hỏi Trợ lý Học vụ")
    st.caption("Thử câu hỏi tự nhiên hoặc chọn một kịch bản demo. Agent sẽ tự quyết định khi nào cần gọi tool.")

    samples = [
        "Tra cứu đầy đủ GPA và CPA của sinh viên SV2026001",
        "Cho tôi xem lịch thi của sinh viên SV2026001",
        "Tra cứu cố vấn và đặt lịch tư vấn cho SV2026001 lúc 14:00 ngày 25/09/2026",
        "Đặt lịch tư vấn học vụ cho tôi",
    ]
    sample = st.selectbox("Kịch bản gợi ý", samples)
    with st.form("agent_form"):
        query = st.text_area("Yêu cầu", value=sample, height=100)
        compare = st.checkbox("So sánh với Chatbot Baseline", value=True)
        submitted = st.form_submit_button("Gửi yêu cầu", type="primary", width="stretch")

    if submitted and query.strip():
        with st.spinner("Agent đang suy luận và gọi công cụ..."):
            baseline_answer = run_baseline_chatbot(query, provider, verbose=False) if compare else None
            trace = run_react_agent(query, provider, mcp_server, verbose=False)
            save_waterfall_trace(trace, append=True)
            agent_answer = get_final_answer(trace)
        if compare:
            left, right = st.columns(2)
            with left:
                st.markdown("#### 💬 Chatbot Baseline")
                st.info(baseline_answer)
                st.caption("Sinh văn bản, không truy cập dữ liệu và không thực hiện hành động.")
            with right:
                st.markdown("#### 🤖 ReAct Agent + MCP")
                st.success(agent_answer)
                st.caption("Tự chọn tool, quan sát dữ liệu thật của demo và hoàn thành hành động.")
        else:
            st.success(agent_answer)
        st.markdown("#### Trace của lượt chạy")
        render_trace(trace)

with tab_gpa:
    st.subheader("Kết quả học tập")
    selected_id = st.selectbox("Sinh viên", list(students), key="gpa_student")
    student = students.get(selected_id, {})
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Sinh viên", student.get("full_name", "—"))
    m2.metric("Lớp", student.get("class", "—"))
    m3.metric("CPA tích lũy", student.get("cpa", "—"))
    m4.metric("Trạng thái", student.get("status", "—"))
    st.caption(f"Cố vấn học tập: {student.get('advisor', '—')} · {student.get('email', '')}")

    semesters = student.get("semesters", [])
    if semesters:
        semester_name = st.selectbox("Học kỳ", [item["semester"] for item in semesters])
        semester = next(item for item in semesters if item["semester"] == semester_name)
        st.metric(f"GPA · {semester_name}", semester.get("gpa", "—"))
        st.dataframe(
            [
                {
                    "Mã môn": item["course_code"],
                    "Tên môn": item["course_name"],
                    "Tín chỉ": item["credits"],
                    "Điểm chữ": item["grade"],
                    "Điểm hệ 4": item["grade_point"],
                }
                for item in semester.get("courses", [])
            ],
            width="stretch",
            hide_index=True,
        )

with tab_exam:
    st.subheader("Lịch thi cá nhân")
    exam_student_id = st.selectbox("Sinh viên", list(students), key="exam_student")
    exam_items = exams.get(exam_student_id, [])
    st.caption(f"Tìm thấy {len(exam_items)} lịch thi trong dữ liệu demo.")
    for item in exam_items:
        with st.container(border=True):
            st.markdown(f"### {item['course_name']} · `{item['course_code']}`")
            c1, c2, c3 = st.columns(3)
            c1.write(f"🗓️ **{item['exam_datetime']}**")
            c2.write(f"📍 Phòng **{item['exam_room']}**")
            c3.write(f"🆔 Lớp thi **{item['exam_class_code']}**")
            st.write(f"**Hình thức:** {item['exam_format']}")
            st.write(f"**Nội dung:** {item['exam_content']}")

with tab_booking:
    st.subheader("Đặt lịch với cố vấn")
    st.caption("Form sẽ gửi yêu cầu qua ReAct Agent: tra cứu đúng cố vấn trước, sau đó gọi tool đặt lịch.")
    with st.form("booking_form"):
        booking_student_id = st.selectbox("Sinh viên", list(students), key="booking_student")
        c1, c2 = st.columns(2)
        booking_date = c1.date_input(
            "Ngày hẹn",
            value=date.today() + timedelta(days=7),
            min_value=date.today(),
        )
        booking_time = c2.time_input("Giờ hẹn", value=time(14, 0))
        booking_submit = st.form_submit_button("Xác nhận đặt lịch", type="primary")
    if booking_submit:
        request = (
            f"Tra cứu cố vấn và đặt lịch tư vấn cho {booking_student_id} lúc "
            f"{booking_time.strftime('%H:%M')} ngày {booking_date.strftime('%d/%m/%Y')}"
        )
        with st.spinner("Đang tra cứu cố vấn và ghi lịch hẹn..."):
            booking_trace = run_react_agent(request, provider, mcp_server, verbose=False)
            save_waterfall_trace(booking_trace, append=True)
        st.success(get_final_answer(booking_trace))
        with st.expander("Xem trace đặt lịch"):
            render_trace(booking_trace)

    st.markdown("#### Lịch đã đặt")
    appointments = _read_json(APPOINTMENTS_PATH, [])
    if appointments:
        st.dataframe(
            [
                {
                    "Mã lịch": item.get("booking_id"),
                    "MSSV": item.get("student_id"),
                    "Thời gian": item.get("datetime"),
                    "Cố vấn": item.get("advisor"),
                    "Tạo lúc": item.get("created_at"),
                }
                for item in reversed(appointments)
            ],
            width="stretch",
            hide_index=True,
        )
    else:
        st.info("Chưa có lịch tư vấn nào được đặt.")

with tab_trace:
    st.subheader("Waterfall Trace · Báo cáo với Lab Coach")
    all_trace = load_trace()
    tool_events = [event for event in all_trace if event.get("action_type") == "TOOL_EXECUTION"]
    t1, t2, t3 = st.columns(3)
    t1.metric("Tổng sự kiện", len(all_trace))
    t2.metric("Tool executions", len(tool_events))
    avg_latency = round(sum(item.get("latency_ms", 0) for item in all_trace) / len(all_trace), 2) if all_trace else 0
    t3.metric("Độ trễ trung bình", f"{avg_latency} ms")

    run_ids = list(dict.fromkeys(event.get("run_id", "legacy") for event in reversed(all_trace)))
    selected_run = st.selectbox("Lọc theo lượt chạy", ["Tất cả"] + run_ids)
    visible_trace = all_trace if selected_run == "Tất cả" else [
        event for event in all_trace if event.get("run_id", "legacy") == selected_run
    ]
    render_trace(visible_trace)
    st.download_button(
        "Tải trace JSON",
        data=json.dumps(visible_trace, ensure_ascii=False, indent=2),
        file_name=f"trace_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
        mime="application/json",
    )
