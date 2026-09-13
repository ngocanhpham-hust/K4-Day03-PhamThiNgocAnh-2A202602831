"""
🛠️ TOOL DEFINITIONS & EXECUTION BACKEND
Mã nguồn chứa danh sách Tool Schemas (JSON Schema) và Execution Layer phục vụ cho MCP Server.
"""

import json
import os
from datetime import datetime
from typing import Dict, Any

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
STUDENTS_PATH = os.path.join(DATA_DIR, "students.json")
EXAMS_PATH = os.path.join(DATA_DIR, "exam_schedule.json")
APPOINTMENTS_PATH = os.path.join(DATA_DIR, "appointments.json")

# ==============================================================================
# 1. KHAI BÁO TOOL SCHEMAS CHUẨN NATIVE JSON SCHEMA (TASK 1.2)
# ==============================================================================

TOOLS_SCHEMA = [
    # Tool 1: Đã được định nghĩa mẫu sẵn cho Học viên tham khảo
    {
        "name": "academic_query",
        "description": "Tra cứu hồ sơ và thông tin học vụ của sinh viên VinUni bằng mã sinh viên.",
        "parameters": {
            "type": "object",
            "properties": {
                "student_id": {
                    "type": "string",
                    "description": "Mã sinh viên cần tra cứu (ví dụ: 'SV2026001')"
                }
            },
            "required": ["student_id"]
        }
    },
    
    # Tool 2: Tra cứu lịch thi theo mã sinh viên.
    {
        "name": "exam_schedule_query",
        "description": "Tra cứu lịch thi đầy đủ của sinh viên VinUni bằng mã sinh viên.",
        "parameters": {
            "type": "object",
            "properties": {
                "student_id": {
                    "type": "string",
                    "description": "Mã sinh viên cần tra cứu lịch thi (ví dụ: 'SV2026001')"
                }
            },
            "required": ["student_id"]
        }
    },

    # Tool 3: Đặt lịch tư vấn. Giữ schema tối giản để dễ quan sát trong demo.
    {
        "name": "schedule_appointment",
        "description": "Đặt lịch hẹn tư vấn học vụ với Cố vấn học tập VinUni.",
        "parameters": {
            "type": "object",
            "properties": {
                "student_id": {
                    "type": "string",
                    "description": "Mã sinh viên cần đặt lịch (ví dụ: 'SV2026001')"
                },
                "datetime_str": {
                    "type": "string",
                    "description": "Thời gian hẹn theo định dạng HH:MM DD/MM/YYYY"
                },
                "advisor_name": {
                    "type": "string",
                    "description": "Tên cố vấn học tập; có thể lấy từ kết quả academic_query"
                }
            },
            "required": ["student_id", "datetime_str", "advisor_name"]
        }
    }
]

# ==============================================================================
# 2. MÔ PHỎNG DỮ LIỆU & HÀM THỰC THI TOOL (EXECUTION LAYER)
# ==============================================================================

def _read_json(path: str, default):
    """Đọc dữ liệu mock từ JSON, trả về giá trị mặc định nếu file chưa tồn tại."""
    try:
        with open(path, "r", encoding="utf-8") as file:
            return json.load(file)
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def _write_json(path: str, data) -> None:
    """Ghi JSON UTF-8 để dữ liệu lịch hẹn tồn tại sau khi tắt ứng dụng."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=2)


def execute_academic_query(student_id: str) -> str:
    """Thực thi tra cứu học vụ theo mã sinh viên"""
    normalized_id = student_id.strip().upper()
    student = _read_json(STUDENTS_PATH, {}).get(normalized_id)
    if student:
        return json.dumps({
            "status": "SUCCESS",
            "student_id": normalized_id,
            "data": student
        }, ensure_ascii=False)
    else:
        return json.dumps({
            "status": "NOT_FOUND",
            "message": f"Không tìm thấy dữ liệu sinh viên có mã '{student_id}'"
        }, ensure_ascii=False)


def execute_exam_schedule_query(student_id: str) -> str:
    """Thực thi tra cứu lịch thi theo mã sinh viên."""
    normalized_id = student_id.strip().upper()
    exams = _read_json(EXAMS_PATH, {}).get(normalized_id)
    if exams:
        return json.dumps({
            "status": "SUCCESS",
            "student_id": normalized_id,
            "total_exams": len(exams),
            "exams": exams
        }, ensure_ascii=False)
    return json.dumps({
        "status": "NOT_FOUND",
        "message": f"Không tìm thấy lịch thi cho sinh viên có mã '{normalized_id}'"
    }, ensure_ascii=False)


def execute_schedule_appointment(student_id: str, datetime_str: str, advisor_name: str) -> str:
    """Đặt lịch hẹn thành công và lưu vào data/appointments.json."""
    normalized_id = student_id.strip().upper()
    appointments = _read_json(APPOINTMENTS_PATH, [])
    booking = {
        "status": "SUCCESS",
        "booking_id": f"BK-{datetime.now().strftime('%Y%m%d%H%M%S%f')}",
        "student_id": normalized_id,
        "datetime": datetime_str,
        "advisor": advisor_name,
        "created_at": datetime.now().astimezone().isoformat(timespec="seconds")
    }
    appointments.append(booking)
    _write_json(APPOINTMENTS_PATH, appointments)
    booking["message"] = (
        f"Đặt lịch thành công cho sinh viên {normalized_id} với {advisor_name} "
        f"vào lúc {datetime_str}."
    )
    return json.dumps(booking, ensure_ascii=False)


# Router gọi tool thực tế
TOOL_ROUTER = {
    "academic_query": execute_academic_query,
    "exam_schedule_query": execute_exam_schedule_query,
    "schedule_appointment": execute_schedule_appointment
}

def dispatch_tool_call(tool_name: str, arguments: Dict[str, Any]) -> str:
    """Hàm trung chuyển thực thi tool"""
    if tool_name in TOOL_ROUTER:
        try:
            return TOOL_ROUTER[tool_name](**arguments)
        except Exception as e:
            return json.dumps({"status": "EXECUTION_ERROR", "error": str(e)}, ensure_ascii=False)
    return json.dumps({"status": "UNKNOWN_TOOL", "error": f"Tool '{tool_name}' không tồn tại!"}, ensure_ascii=False)
