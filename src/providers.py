"""
🔌 MULTI-PROVIDER LLM ADAPTER (Google Gemini, OpenAI & Offline Mock)
Hỗ trợ Native Tool Calling và chuyển đổi linh hoạt qua biến môi trường LLM_PROVIDER.
"""

import os
import sys
import json
import re
import time
from typing import Dict, Any, List
from dotenv import load_dotenv

if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

load_dotenv()

class BaseLLMProvider:
    """Interface cơ sở cho các LLM Provider hỗ trợ Native Tool Calling"""
    def generate(self, prompt: str, system_prompt: str = "") -> str:
        raise NotImplementedError

    def generate_with_tools(self, prompt: str, tools_schema: List[Dict[str, Any]], system_prompt: str = "") -> Dict[str, Any]:
        raise NotImplementedError


class MockOfflineProvider(BaseLLMProvider):
    """Offline Mock Provider dùng để chạy thử mà không tốn API Key"""
    def __init__(self):
        self.model_name = "Offline-Mock-Model-2026"

    def generate(self, prompt: str, system_prompt: str = "") -> str:
        return f"[Mock Chatbot Response]: Xin chào! Tôi đã nhận được câu hỏi '{prompt}'. (Chế độ Chatbot không có Tool tra cứu dữ liệu thời gian thực)."

    def generate_with_tools(self, prompt: str, tools_schema: List[Dict[str, Any]], system_prompt: str = "") -> Dict[str, Any]:
        original_query = prompt.split("\n\nLỊCH SỬ THỰC THI", 1)[0]
        query_lower = original_query.lower()
        student_match = re.search(r"\bsv\d+\b", original_query, re.IGNORECASE)
        student_id = student_match.group(0).upper() if student_match else None

        observations = []
        if "<OBSERVATIONS_JSON>" in prompt:
            raw = prompt.split("<OBSERVATIONS_JSON>", 1)[1].split("</OBSERVATIONS_JSON>", 1)[0]
            try:
                observations = json.loads(raw)
            except json.JSONDecodeError:
                observations = []

        completed_tools = [item.get("tool_name") for item in observations]
        last_result = observations[-1].get("result", {}) if observations else {}
        if last_result.get("status") == "NOT_FOUND":
            return {
                "type": "text",
                "content": last_result.get("message", "Không tìm thấy dữ liệu phù hợp."),
                "thought": "Tool trả về NOT_FOUND nên tôi phản hồi đúng dữ liệu quan sát và không suy đoán."
            }

        if "đặt lịch" in query_lower or "lịch hẹn" in query_lower:
            if not student_id:
                return {
                    "type": "text",
                    "content": "Bạn vui lòng cung cấp mã sinh viên để mình hỗ trợ đặt lịch tư vấn.",
                    "thought": "Yêu cầu đặt lịch còn thiếu mã sinh viên nên cần hỏi lại."
                }
            date_match = re.search(r"\b\d{1,2}/\d{1,2}/\d{4}\b", original_query)
            time_match = re.search(r"\b\d{1,2}:\d{2}(?:\s*(?:AM|PM))?\b", original_query, re.IGNORECASE)
            if not date_match or not time_match:
                return {
                    "type": "text",
                    "content": "Bạn muốn gặp cố vấn vào ngày và giờ cụ thể nào? Vui lòng cho mình thời gian theo định dạng HH:MM DD/MM/YYYY.",
                    "thought": "Yêu cầu đặt lịch còn thiếu ngày hoặc giờ nên cần hỏi lại."
                }
            if "academic_query" not in completed_tools:
                return {
                    "type": "tool_call",
                    "tool_name": "academic_query",
                    "arguments": {"student_id": student_id},
                    "thought": "Cần tra cứu hồ sơ để xác định đúng cố vấn trước khi đặt lịch."
                }
            if "schedule_appointment" not in completed_tools:
                academic = next(
                    (item.get("result", {}) for item in observations if item.get("tool_name") == "academic_query"),
                    {}
                )
                advisor = academic.get("data", {}).get("advisor", "Cố vấn học tập")
                datetime_str = f"{time_match.group(0).upper().replace(' AM', '').replace(' PM', '')} {date_match.group(0)}"
                return {
                    "type": "tool_call",
                    "tool_name": "schedule_appointment",
                    "arguments": {
                        "student_id": student_id,
                        "datetime_str": datetime_str,
                        "advisor_name": advisor
                    },
                    "thought": "Đã có tên cố vấn từ Observation; tiếp tục gọi tool đặt lịch để hoàn thành mục tiêu."
                }
            appointment = next(
                (item.get("result", {}) for item in observations if item.get("tool_name") == "schedule_appointment"),
                {}
            )
            return {
                "type": "text",
                "content": appointment.get("message", "Lịch tư vấn đã được đặt thành công."),
                "thought": "Cả bước tra cứu cố vấn và đặt lịch đều đã hoàn tất."
            }

        if "lịch thi" in query_lower or re.search(r"\bthi\b", query_lower):
            if not student_id:
                return {
                    "type": "text",
                    "content": "Bạn vui lòng cung cấp mã sinh viên để mình tra cứu lịch thi.",
                    "thought": "Thiếu mã sinh viên nên cần hỏi lại trước khi gọi tool."
                }
            if "exam_schedule_query" not in completed_tools:
                return {
                    "type": "tool_call",
                    "tool_name": "exam_schedule_query",
                    "arguments": {"student_id": student_id},
                    "thought": "Người dùng cần dữ liệu lịch thi nên tôi gọi tool exam_schedule_query."
                }
            exams = last_result.get("exams", [])
            lines = [f"Lịch thi của {student_id} gồm {len(exams)} môn:"]
            for exam in exams:
                lines.append(
                    f"- {exam['course_name']} ({exam['course_code']}), {exam['exam_datetime']}, "
                    f"phòng {exam['exam_room']}, lớp thi {exam['exam_class_code']}; "
                    f"{exam['exam_format']}; {exam['exam_content']}."
                )
            return {
                "type": "text",
                "content": "\n".join(lines),
                "thought": "Đã có đầy đủ lịch thi từ Observation nên tôi tổng hợp câu trả lời."
            }

        if student_id or "tra cứu" in query_lower or "gpa" in query_lower or "cpa" in query_lower:
            if not student_id:
                return {
                    "type": "text",
                    "content": "Bạn vui lòng cung cấp mã sinh viên để mình tra cứu thông tin học vụ.",
                    "thought": "Thiếu mã sinh viên nên cần hỏi lại trước khi gọi tool."
                }
            if "academic_query" not in completed_tools:
                return {
                    "type": "tool_call",
                    "tool_name": "academic_query",
                    "arguments": {"student_id": student_id},
                    "thought": "Người dùng muốn tra cứu hồ sơ và điểm nên tôi gọi tool academic_query."
                }
            student = last_result.get("data", {})
            lines = [
                f"Kết quả học tập của {student.get('full_name', '')} ({student_id}): CPA {student.get('cpa', '')}."
            ]
            for semester in student.get("semesters", []):
                courses = ", ".join(
                    f"{course['course_name']} ({course['course_code']}): {course['grade']}"
                    for course in semester.get("courses", [])
                )
                lines.append(f"- {semester['semester']}: GPA {semester['gpa']}; {courses}.")
            return {
                "type": "text",
                "content": "\n".join(lines),
                "thought": "Đã nhận đủ hồ sơ và bảng điểm từ Observation nên tôi tổng hợp câu trả lời."
            }

        return {
            "type": "text",
            "content": "Đây là bản demo trợ lý học vụ. Mình có thể tra cứu GPA/CPA, lịch thi và hỗ trợ đặt lịch với cố vấn.",
            "thought": "Câu hỏi chung có thể trả lời trực tiếp mà không cần gọi tool."
        }


class GeminiProvider(BaseLLMProvider):
    """Google Gemini Provider (Native Tool Calling với Google GenAI SDK)"""
    def __init__(self, api_key: str = None, model: str = None):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        self.model_name = model or os.getenv("LLM_MODEL") or "gemini-2.5-flash"
        self._api_retry_depth = 0

    def generate(self, prompt: str, system_prompt: str = "") -> str:
        if not self.api_key or self.api_key == "your_gemini_api_key_here":
            return "[Gemini Error]: Chưa cấu hình GEMINI_API_KEY trong file .env! Đang sử dụng chế độ Mock."
        try:
            from google import genai
            client = genai.Client(api_key=self.api_key)
            contents = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt
            response = client.models.generate_content(model=self.model_name, contents=contents)
            return response.text
        except Exception as e:
            return f"[Gemini Exception]: {str(e)}"

    def generate_with_tools(self, prompt: str, tools_schema: List[Dict[str, Any]], system_prompt: str = "") -> Dict[str, Any]:
        if not self.api_key or self.api_key == "your_gemini_api_key_here":
            print("ℹ️ [Gemini Provider]: Chưa tìm thấy GEMINI_API_KEY hợp lệ. Tự động chuyển sang Mock Offline.")
            return MockOfflineProvider().generate_with_tools(prompt, tools_schema, system_prompt)
        
        try:
            from google import genai
            from google.genai import types

            client = genai.Client(api_key=self.api_key)
            
            # Chuẩn hóa function declarations cho Gemini SDK
            function_declarations = []
            for tool in tools_schema:
                # Bỏ qua các tool schema chưa được định nghĩa hoàn chỉnh
                if not tool.get("name") or not tool.get("parameters"):
                    continue
                function_declarations.append({
                    "name": tool["name"],
                    "description": tool.get("description", ""),
                    "parameters": tool.get("parameters", {})
                })

            config = types.GenerateContentConfig(
                system_instruction=system_prompt if system_prompt else None,
                tools=[{"function_declarations": function_declarations}] if function_declarations else None,
                temperature=0.2
            )

            response = client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=config
            )

            # Kiểm tra xem Gemini có trả về Tool Call không
            if response.function_calls:
                call = response.function_calls[0]
                args = dict(call.args) if hasattr(call, 'args') and call.args else {}
                return {
                    "type": "tool_call",
                    "tool_name": call.name,
                    "arguments": args,
                    "thought": f"Gemini quyết định gọi công cụ '{call.name}' với tham số: {json.dumps(args, ensure_ascii=False)}"
                }
            else:
                return {
                    "type": "text",
                    "content": response.text or "",
                    "thought": "Gemini phản hồi trực tiếp bằng văn bản (không cần gọi công cụ)."
                }

        except Exception as e:
            error_text = str(e)
            is_rate_limit = "429" in error_text or "RESOURCE_EXHAUSTED" in error_text
            is_daily_quota = "PerDay" in error_text or "per day" in error_text.lower()
            is_transient = any(
                marker in error_text.lower()
                for marker in ("server disconnected", "timed out", "connection reset", "temporarily unavailable")
            )
            if ((is_rate_limit and not is_daily_quota) or is_transient) and self._api_retry_depth < 2:
                retry_match = re.search(r"retry in\s+([\d.]+)s", error_text, re.IGNORECASE)
                wait_seconds = min(
                    60.0,
                    (float(retry_match.group(1)) + 2) if retry_match else (3.0 if is_transient else 60.0)
                )
                print(f"⏳ [Gemini Retry]: Chờ {wait_seconds:.1f}s rồi thử lại...")
                self._api_retry_depth += 1
                try:
                    time.sleep(wait_seconds)
                    return self.generate_with_tools(prompt, tools_schema, system_prompt)
                finally:
                    self._api_retry_depth -= 1
            print(f"⚠️ [Gemini API Warning]: Không thể kết nối live API ({error_text}). Tự động fallback về Mock.")
            fallback = MockOfflineProvider().generate_with_tools(prompt, tools_schema, system_prompt)
            fallback["llm_source"] = "mock_fallback"
            fallback["api_error"] = error_text
            return fallback


class OpenAIProvider(BaseLLMProvider):
    """OpenAI Provider (Native Tool Calling với OpenAI SDK)"""
    def __init__(self, api_key: str = None, model: str = None):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.model_name = model or os.getenv("LLM_MODEL") or "gpt-4o-mini"

    def generate(self, prompt: str, system_prompt: str = "") -> str:
        if not self.api_key or self.api_key == "your_openai_api_key_here":
            return "[OpenAI Error]: Chưa cấu hình OPENAI_API_KEY trong file .env! Đang sử dụng chế độ Mock."
        try:
            from openai import OpenAI
            client = OpenAI(api_key=self.api_key)
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})
            response = client.chat.completions.create(model=self.model_name, messages=messages)
            return response.choices[0].message.content or ""
        except Exception as e:
            return f"[OpenAI Exception]: {str(e)}"

    def generate_with_tools(self, prompt: str, tools_schema: List[Dict[str, Any]], system_prompt: str = "") -> Dict[str, Any]:
        if not self.api_key or self.api_key == "your_openai_api_key_here":
            print("ℹ️ [OpenAI Provider]: Chưa tìm thấy OPENAI_API_KEY hợp lệ. Tự động chuyển sang Mock Offline.")
            return MockOfflineProvider().generate_with_tools(prompt, tools_schema, system_prompt)

        try:
            from openai import OpenAI
            client = OpenAI(api_key=self.api_key)

            tools = []
            for tool in tools_schema:
                if not tool.get("name"):
                    continue
                tools.append({
                    "type": "function",
                    "function": {
                        "name": tool["name"],
                        "description": tool.get("description", ""),
                        "parameters": tool.get("parameters", {})
                    }
                })

            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})

            response = client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                tools=tools if tools else None,
                tool_choice="auto" if tools else None
            )

            msg = response.choices[0].message
            if msg.tool_calls:
                call = msg.tool_calls[0]
                args = json.loads(call.function.arguments) if call.function.arguments else {}
                return {
                    "type": "tool_call",
                    "tool_name": call.function.name,
                    "arguments": args,
                    "thought": f"OpenAI quyết định gọi công cụ '{call.function.name}' với tham số: {json.dumps(args, ensure_ascii=False)}"
                }
            else:
                return {
                    "type": "text",
                    "content": msg.content or "",
                    "thought": "OpenAI phản hồi trực tiếp bằng văn bản (không cần gọi công cụ)."
                }
        except Exception as e:
            print(f"⚠️ [OpenAI API Warning]: Không thể kết nối live API ({str(e)}). Tự động fallback về Mock.")
            return MockOfflineProvider().generate_with_tools(prompt, tools_schema, system_prompt)


def get_llm_provider() -> BaseLLMProvider:
    """Factory function khởi tạo Provider theo LLM_PROVIDER env variable"""
    provider_type = os.getenv("LLM_PROVIDER", "gemini").lower()
    
    if provider_type == "gemini":
        key = os.getenv("GEMINI_API_KEY")
        if key and key != "your_gemini_api_key_here":
            return GeminiProvider()
        else:
            return MockOfflineProvider()
    elif provider_type == "openai":
        key = os.getenv("OPENAI_API_KEY")
        if key and key != "your_openai_api_key_here":
            return OpenAIProvider()
        else:
            return MockOfflineProvider()
    elif provider_type == "mock":
        return MockOfflineProvider()
    else:
        return MockOfflineProvider()
