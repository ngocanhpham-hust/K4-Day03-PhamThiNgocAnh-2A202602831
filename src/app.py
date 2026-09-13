"""
🚀 CORE AGENT APPLICATION (DAY 03: CHATBOT VS REACT AGENT)
Thực thi so sánh giữa Chatbot Baseline (Cấp 2) và ReAct Agent kết nối MCP Server (Cấp 3).
"""

import json
import os
import sys
import time
import uuid
from datetime import datetime
from dotenv import load_dotenv

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

from mcp_server import MCPAcademicServer
from prompts import (
    CHATBOT_BASELINE_PROMPT,
    REACT_AGENT_SYSTEM_PROMPT,
    MAX_ITERATIONS
)
from providers import get_llm_provider

load_dotenv()

def load_test_cases():
    """Tải danh sách 5 test cases từ config/test_cases.json hoặc config/test_cases.example.json"""
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    config_path = os.path.join(base_dir, "config", "test_cases.json")
    if not os.path.exists(config_path):
        example_path = os.path.join(base_dir, "config", "test_cases.example.json")
        if os.path.exists(example_path):
            print("⚠️ [CONFIG NOTICE]: Chưa thấy file 'config/test_cases.json'. Đang dùng mẫu 'config/test_cases.example.json'.")
            print("👉 Hãy chạy: copy config/test_cases.example.json config/test_cases.json và viết test cases theo đề tài của bạn!\n")
            config_path = example_path
        else:
            config_path = "test_cases.json"
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_waterfall_trace(trace_data: list, append: bool = False):
    """Ghi vết log Waterfall Trace Log ra file docs/trace_waterfall.json"""
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    docs_dir = os.path.join(base_dir, "docs")
    os.makedirs(docs_dir, exist_ok=True)
    trace_path = os.path.join(docs_dir, "trace_waterfall.json")
    output = trace_data
    if append and os.path.exists(trace_path):
        try:
            with open(trace_path, "r", encoding="utf-8") as f:
                existing = json.load(f)
            output = existing + trace_data if isinstance(existing, list) else trace_data
        except (json.JSONDecodeError, OSError):
            output = trace_data
    with open(trace_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"📊 [OBSERVABILITY]: Đã lưu {len(trace_data)} sự kiện Waterfall Trace tại '{trace_path}'!")
    return trace_path


def run_baseline_chatbot(user_query: str, provider, verbose: bool = True) -> str:
    """Chạy Chatbot gốc (Cấp 2) không có công cụ gọi Tool"""
    if verbose:
        print(f"\n💬 [CHATBOT BASELINE] Câu hỏi: {user_query}")
    response = provider.generate(user_query, system_prompt=CHATBOT_BASELINE_PROMPT)
    if verbose:
        print(f"🤖 Chatbot phản hồi:\n{response}")
    return response


def _fallback_answer(observations: list) -> str:
    """Tổng hợp có tính quyết định khi provider lặp tool hoặc hết số vòng."""
    if not observations:
        return "Mình chưa có đủ dữ liệu để hoàn thành yêu cầu. Bạn vui lòng bổ sung thông tin."
    result = observations[-1].get("result", {})
    if result.get("status") == "NOT_FOUND":
        return result.get("message", "Không tìm thấy dữ liệu phù hợp.")
    if result.get("status") not in (None, "SUCCESS"):
        return result.get("message") or result.get("error") or "Công cụ không thể xử lý yêu cầu."
    if result.get("message"):
        return result["message"]
    if "exams" in result:
        lines = [f"Lịch thi của {result.get('student_id', '')} gồm {len(result['exams'])} môn:"]
        for exam in result["exams"]:
            lines.append(
                f"- {exam['course_name']} ({exam['course_code']}), {exam['exam_datetime']}, "
                f"phòng {exam['exam_room']}, lớp {exam['exam_class_code']}; "
                f"{exam['exam_format']}; {exam['exam_content']}."
            )
        return "\n".join(lines)
    if "data" in result:
        student = result["data"]
        lines = [
            f"{student.get('full_name', '')} ({result.get('student_id', '')}) – "
            f"lớp {student.get('class', '')}, CPA {student.get('cpa', '')}, "
            f"cố vấn {student.get('advisor', '')}."
        ]
        for semester in student.get("semesters", []):
            course_text = ", ".join(
                f"{course['course_name']} ({course['course_code']}): {course['grade']}"
                for course in semester.get("courses", [])
            )
            lines.append(f"- {semester['semester']}: GPA {semester['gpa']}; {course_text}.")
        return "\n".join(lines)
    return json.dumps(result, ensure_ascii=False)


def get_final_answer(trace_logs: list) -> str:
    """Lấy câu trả lời cuối để CLI/UI dùng chung."""
    for event in reversed(trace_logs):
        if event.get("action_type") == "FINAL_ANSWER":
            return event.get("output", "")
    return ""


def _clean_user_answer(content: str) -> str:
    """Ẩn tiền tố suy luận nếu model vô tình đưa Thought vào câu trả lời người dùng."""
    cleaned = (content or "").strip()
    if cleaned.lower().startswith("thought:"):
        non_empty_lines = [line.strip() for line in cleaned.splitlines() if line.strip()]
        if len(non_empty_lines) > 1:
            return non_empty_lines[-1]
    return cleaned


def run_react_agent(
    user_query: str,
    provider,
    mcp_server: MCPAcademicServer,
    verbose: bool = True
) -> list:
    """
    [REACT AGENT LOOP] Thực thi vòng lặp Thought -> Action -> Observation với MCP Server
    Trả về danh sách trace log của phiên thực thi.
    """
    if verbose:
        print(f"\n🤖 [REACT AGENT] Câu hỏi: {user_query}")
    
    step = 0
    trace_logs = []
    observations = []
    executed_calls = set()
    run_id = uuid.uuid4().hex[:10]
    tools_list = mcp_server.list_tools()
    
    while step < MAX_ITERATIONS:
        step += 1
        step_start_time = time.time()
        if verbose:
            print(f"\n--- 🔄 Vòng lặp ReAct Loop (Step {step}/{MAX_ITERATIONS}) ---")

        agent_prompt = user_query
        if observations:
            agent_prompt += (
                "\n\nLỊCH SỬ THỰC THI (không gọi lại tool đã hoàn tất với cùng tham số):\n"
                f"<OBSERVATIONS_JSON>{json.dumps(observations, ensure_ascii=False)}</OBSERVATIONS_JSON>\n"
                "Dựa trên yêu cầu ban đầu và Observation, hãy gọi tool tiếp theo nếu mục tiêu chưa xong; "
                "nếu đã xong, hãy trả lời cuối cùng bằng tiếng Việt."
            )
        
        # Gọi LLM với Native Tool Calling Specs
        llm_response = provider.generate_with_tools(agent_prompt, tools_list, system_prompt=REACT_AGENT_SYSTEM_PROMPT)
        latency_ms = round((time.time() - step_start_time) * 1000, 2)
        
        thought = llm_response.get("thought", "Đang suy luận...")
        llm_source = llm_response.get("llm_source", provider.__class__.__name__)
        if verbose:
            print(f"🧠 [Thought]: {thought}")
        
        # Trường hợp 1: LLM quyết định trả lời bằng văn bản trực tiếp
        if llm_response.get("type") == "text":
            final_content = _clean_user_answer(llm_response.get("content", ""))
            if verbose:
                print(f"🏁 [Final Answer]: {final_content}")
            trace_logs.append({
                "run_id": run_id,
                "timestamp": datetime.now().astimezone().isoformat(timespec="seconds"),
                "step": step,
                "query": user_query,
                "action_type": "FINAL_ANSWER",
                "llm_provider": provider.__class__.__name__,
                "llm_source": llm_source,
                "thought": thought,
                "output": final_content,
                "latency_ms": latency_ms
            })
            break
            
        # Trường hợp 2: LLM đề xuất gọi Tool (Action)
        elif llm_response.get("type") == "tool_call":
            tool_name = llm_response.get("tool_name")
            arguments = llm_response.get("arguments", {})
            call_signature = (tool_name, json.dumps(arguments, ensure_ascii=False, sort_keys=True))
            if call_signature in executed_calls:
                final_content = _fallback_answer(observations)
                if verbose:
                    print("⚠️ [Loop Guard]: Tool call bị lặp; tổng hợp từ Observation hiện có.")
                    print(f"🏁 [Final Answer]: {final_content}")
                trace_logs.append({
                    "run_id": run_id,
                    "timestamp": datetime.now().astimezone().isoformat(timespec="seconds"),
                    "step": step,
                    "query": user_query,
                    "action_type": "FINAL_ANSWER",
                    "llm_provider": provider.__class__.__name__,
                    "llm_source": llm_source,
                    "thought": "Dừng tool call trùng lặp và tổng hợp từ dữ liệu đã quan sát.",
                    "output": final_content,
                    "latency_ms": latency_ms
                })
                break
            executed_calls.add(call_signature)

            if verbose:
                print(f"🛠️ [Action Proposed]: {tool_name}({arguments})")
            
            # Thực thi Tool qua MCP Server
            mcp_result = mcp_server.call_tool(tool_name, arguments)
            obs_data = mcp_result.get("result") or mcp_result.get("error", {})
            if verbose:
                print(f"👁️ [Observation từ MCP Server]: {json.dumps(obs_data, ensure_ascii=False)}")

            observations.append({"tool_name": tool_name, "arguments": arguments, "result": obs_data})
            trace_logs.append({
                "run_id": run_id,
                "timestamp": datetime.now().astimezone().isoformat(timespec="seconds"),
                "step": step,
                "query": user_query,
                "action_type": "TOOL_EXECUTION",
                "llm_provider": provider.__class__.__name__,
                "llm_source": llm_source,
                "thought": thought,
                "tool_name": tool_name,
                "arguments": arguments,
                "observation": obs_data,
                "latency_ms": latency_ms
            })

            appointment_intent = "đặt lịch" in user_query.lower() or "lịch hẹn" in user_query.lower()
            goal_complete = (
                obs_data.get("status") != "SUCCESS"
                or tool_name in ("exam_schedule_query", "schedule_appointment")
                or (tool_name == "academic_query" and not appointment_intent)
            )
            if goal_complete:
                final_content = _fallback_answer(observations)
                completion_thought = "Observation đã đủ để hoàn thành mục tiêu; tổng hợp câu trả lời không bịa thêm dữ liệu."
                if verbose:
                    print(f"🧠 [Thought]: {completion_thought}")
                    print(f"🏁 [Final Answer]: {final_content}")
                trace_logs.append({
                    "run_id": run_id,
                    "timestamp": datetime.now().astimezone().isoformat(timespec="seconds"),
                    "step": step + 1,
                    "query": user_query,
                    "action_type": "FINAL_ANSWER",
                    "llm_provider": provider.__class__.__name__,
                    "llm_source": "deterministic_observation_synthesis",
                    "thought": completion_thought,
                    "output": final_content,
                    "latency_ms": 0.0
                })
                break

        else:
            final_content = "Provider trả về phản hồi không hợp lệ; vui lòng thử lại."
            trace_logs.append({
                "run_id": run_id,
                "timestamp": datetime.now().astimezone().isoformat(timespec="seconds"),
                "step": step,
                "query": user_query,
                "action_type": "FINAL_ANSWER",
                "llm_provider": provider.__class__.__name__,
                "llm_source": llm_source,
                "thought": "Không nhận diện được kiểu phản hồi của provider.",
                "output": final_content,
                "latency_ms": latency_ms
            })
            break

    if not get_final_answer(trace_logs):
        final_content = _fallback_answer(observations)
        trace_logs.append({
            "run_id": run_id,
            "timestamp": datetime.now().astimezone().isoformat(timespec="seconds"),
            "step": step + 1,
            "query": user_query,
            "action_type": "FINAL_ANSWER",
            "llm_provider": provider.__class__.__name__,
            "llm_source": "deterministic_fallback",
            "thought": "Đạt giới hạn vòng lặp; tổng hợp an toàn từ Observation hiện có.",
            "output": final_content,
            "latency_ms": 0.0
        })
        if verbose:
            print(f"🏁 [Final Answer]: {final_content}")

    return trace_logs


if __name__ == "__main__":
    print("==========================================================")
    print("🏫 VINUNI AI COURSE - DAY 03 LAB: CHATBOT VS REACT AGENT")
    print("==========================================================")
    
    provider = get_llm_provider()
    mcp_server = MCPAcademicServer()
    
    print(f"🔌 LLM Provider: {provider.__class__.__name__}")
    print(f"🌐 MCP Server: {mcp_server.server_name}\n")
    
    tests = load_test_cases()
    print(f"✅ Đã tải thành công {len(tests)} Test Cases thử nghiệm.\n")
    
    if "--interactive" in sys.argv:
        print("🎮 [INTERACTIVE MODE] Trò chuyện trực tiếp với ReAct Agent:")
        print("💡 Gợi ý câu hỏi thử nghiệm:")
        print("   - Câu hỏi chung: 'Quy chế học vụ VinUni yêu cầu bao nhiêu tín chỉ?'")
        print("   - Tra cứu học vụ: 'Hãy tra cứu thông tin học vụ của sinh viên SV2026001'")
        print("   - Đặt lịch hẹn: 'Đặt lịch hẹn tư vấn cho SV2026001 vào 14:00 ngày 15/09/2026'")
        print("   - Gõ 'exit' hoặc 'quit' để kết thúc phiên trò chuyện.\n")
        while True:
            try:
                user_input = input("👤 Sinh viên hỏi: ").strip()
                if not user_input or user_input.lower() in ["exit", "quit"]:
                    print("👋 Tạm biệt! Kết thúc phiên trò chuyện.")
                    break
                logs = run_react_agent(user_input, provider, mcp_server)
                save_waterfall_trace(logs)
            except (KeyboardInterrupt, EOFError):
                print("\n👋 Đã thoát phiên tương tác.")
                break
    elif "--all" in sys.argv:
        print("🚀 [TEST SUITE MODE] Kiểm tra 5 Test Cases:")
        completed_count = 0
        todo_count = 0
        all_traces = []
        
        for tc in tests:
            print(f"\n==================================================")
            print(f"🧪 [{tc['id']}] Loại test: {tc['type']} (Độ phức tạp: {tc['complexity']})")
            print(f"📌 Kỳ vọng: {tc['expected_behavior']}")
            
            if tc["question"].strip().startswith("TODO"):
                print(f"⏸️ [CHƯA KÍCH HOẠT - ĐANG LÀ TODO]:")
                print(f"   {tc['question']}")
                print(f"   👉 Hãy mở file 'config/test_cases.json' để viết câu hỏi thực tế cho Test Case này!")
                todo_count += 1
            else:
                logs = run_react_agent(tc["question"], provider, mcp_server)
                all_traces.extend(logs)
                completed_count += 1
                
        print(f"\n==================================================")
        print(f"📊 [KẾT QUẢ TEST SUITE]: Đã thực thi {completed_count}/{len(tests)} Test Cases | {todo_count} Test Cases đang chờ điền câu hỏi (TODO)")
        if all_traces:
            save_waterfall_trace(all_traces)
        print(f"💡 Để trò chuyện trực tiếp từng câu: Chạy 'python src/app.py --interactive'")
    else:
        # Chế độ mặc định khi chỉ gõ 'python src/app.py'
        print("ℹ️ HƯỚNG DẪN SỬ DỤNG CHƯƠNG TRÌNH:")
        print("  1. Chat trực tiếp liên tục:   python src/app.py --interactive")
        print("  2. Chạy toàn bộ Test Cases:    python src/app.py --all\n")
        
        sample_query = tests[1]["question"]
        print(f"--- 🏁 DEMO CHẠY THỬ 1 TEST CASE MẪU (TC02: Tra cứu học vụ) ---")
        logs = run_react_agent(sample_query, provider, mcp_server)
        save_waterfall_trace(logs)
        print("\n💡 Hãy thử ngay lệnh: python src/app.py --interactive để chat trực tiếp!")
