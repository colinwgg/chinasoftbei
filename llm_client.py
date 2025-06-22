# ===============================
# spark_llm_client.py - 星火大模型模块
# ===============================
import base64
import hashlib
import hmac
import json
import ssl
from time import mktime, sleep
from urllib.parse import urlparse, urlencode
from wsgiref.handlers import format_date_time
import websocket

APPID = "777b23bb"
API_KEY = "f1935f643ee6f8de9ad503940e8497d8"
API_SECRET = "ZGIxOGFiNjBjNjBkYjZiMmUyYTIwYTM1"
DOMAIN = "x1"
SPARK_URL = "wss://spark-api.xf-yun.com/v1/x1"


def _build_url():
    now = format_date_time(mktime(time.localtime()))
    signature_origin = f"host: spark-api.xf-yun.com\ndate: {now}\nGET /v1/x1 HTTP/1.1"
    signature_sha = hmac.new(API_SECRET.encode(), signature_origin.encode(), hashlib.sha256).digest()
    signature = base64.b64encode(signature_sha).decode()
    auth = f'api_key="{API_KEY}", algorithm="hmac-sha256", headers="host date request-line", signature="{signature}"'
    auth_base64 = base64.b64encode(auth.encode()).decode()
    query = urlencode({"authorization": auth_base64, "date": now, "host": "spark-api.xf-yun.com"})
    return f"{SPARK_URL}?{query}"


def _chat_stream(prompt):
    done = threading.Event()
    result = []

    def on_message(ws, message):
        data = json.loads(message)
        choices = data.get("payload", {}).get("choices", {})
        text = choices.get("text", [{}])[0].get("content", "")
        result.append(text)
        if choices.get("status") == 2:
            ws.close()
            done.set()

    def on_error(ws, error):
        print("LLM错误:", error)
        done.set()

    def on_close(ws, *_):
        done.set()

    def on_open(ws):
        ws.send(json.dumps({
            "header": {"app_id": APPID, "uid": "user1"},
            "parameter": {
                "chat": {"domain": DOMAIN, "temperature": 0.8, "max_tokens": 4096}
            },
            "payload": {"message": {"text": prompt}}
        }))

    ws = websocket.WebSocketApp(_build_url(),
                                 on_message=on_message,
                                 on_error=on_error,
                                 on_close=on_close,
                                 on_open=on_open)
    ws.run_forever(sslopt={"cert_reqs": ssl.CERT_NONE})
    done.wait(timeout=60)
    return ''.join(result).strip()


def generate_questions(resume_text, job):
    prompt = f"""
    请你基于以下简历内容和岗位"{job}"生成5个中文面试问题：\n\n简历内容：{resume_text}\n\n问题：
    """
    raw = _chat_stream(prompt)
    return [q.strip() for q in raw.split('\n') if q.strip() and len(q) < 100]


def evaluate_answer(question, answer_text):
    prompt = f"""
    你是HR专家，请根据如下内容对面试回答进行打分并返回如下JSON：\n\n面试问题：{question}\n候选人回答：{answer_text}\n
    JSON格式：\n{{\n  \"score\": 整数0~100,\n  \"strengths\": \"一句话优点\",\n  \"weaknesses\": \"一句话建议\"\n}}
    """
    raw = _chat_stream(prompt)
    try:
        return json.loads(raw.strip().replace('```json', '').replace('```', ''))
    except:
        return {"score": 0, "strengths": "未识别", "weaknesses": "格式错误"}


def generate_report(results):
    total = 0
    count = 0
    for r in results:
        try:
            total += int(r['evaluation']['score'])
            count += 1
        except:
            continue
    avg = round(total / count) if count else 0
    return f"本次面试平均分为 {avg} 分，建议根据反馈逐项改进，提升表达清晰度和专业匹配度。"
