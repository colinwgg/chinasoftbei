import os
import time
import json
import base64
import hashlib
import hmac
import requests
import urllib.parse
import ssl # 用于WebSocket连接
import threading # 用于同步等待WebSocket结果

from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from wsgiref.handlers import format_date_time
from datetime import datetime # 导入 datetime 类
from time import mktime # 导入 mktime 函数
from pydub import AudioSegment # 确保已安装 pydub
import websocket # 确保已安装 websocket-client
from pdfminer.high_level import extract_text
from werkzeug.utils import secure_filename

# =====================================================================================
# 1. FLASK 应用设置
# =====================================================================================

app = Flask(__name__)
app.secret_key = 'a_different_secret_key_for_this_approach' # 请确保设置一个强密钥

# 定义录音文件和转写结果文件的存储目录
RECORDINGS_DIR = 'static/recordings' # 录音文件存放处 (Flask可以直接访问)
ANSWERS_DIR = 'answers' # 转写结果文本文件存放处 (服务器内部使用)
UPLOAD_TEMP_DIR = 'temp_uploads'

if not os.path.exists(RECORDINGS_DIR):
    os.makedirs(RECORDINGS_DIR)
if not os.path.exists(ANSWERS_DIR):
    os.makedirs(ANSWERS_DIR)

# =====================================================================================
# 2. 讯飞 API 密钥配置
# =====================================================================================
LFASR_APPID = os.environ.get("LFASR_APPID", "777b23bb")
LFASR_SECRET_KEY = os.environ.get("LFASR_SECRET_KEY", "b1f7053fc49faebf828a76f317423cd7")

SPARK_APPID = os.environ.get("SPARK_APPID", "777b23bb")
SPARK_API_KEY = os.environ.get("SPARK_API_KEY", "f1935f643ee6f8de9ad503940e8497d8")
SPARK_API_SECRET = os.environ.get("SPARK_API_SECRET", "ZGIxOGFiNjBjNjBkYjZiMmUyYTIwYTM1")

# 星火大模型服务地址和领域
SPARK_URL = "wss://spark-api.xf-yun.com/v1/x1" 
SPARK_DOMAIN = "x1" 

# =====================================================================================
# 3. 讯飞长语音转写 API 客户端
# =====================================================================================
lfasr_host = 'https://raasr.xfyun.cn/v2/api'
api_upload = '/upload'
api_get_result = '/getResult'

class LongAudioRequestApi(object): # 重命名类名，避免与Flask的request混淆
    def __init__(self, appid, secret_key, upload_file_path):
        self.appid = appid
        self.secret_key = secret_key
        self.upload_file_path = upload_file_path
        self.ts = str(int(time.time()))
        self.signa = self.get_signa()

    def get_signa(self):
        m2 = hashlib.md5()
        m2.update((self.appid + self.ts).encode('utf-8'))
        md5 = m2.hexdigest()
        md5 = bytes(md5, encoding='utf-8')
        signa = hmac.new(self.secret_key.encode('utf-8'), md5, hashlib.sha1).digest()
        signa = base64.b64encode(signa)
        signa = str(signa, 'utf-8')
        return signa

    def upload(self):
        print("长语音转写：上传部分：")
        upload_file_path = self.upload_file_path
        file_len = os.path.getsize(upload_file_path)
        file_name = os.path.basename(upload_file_path)

        param_dict = {}
        param_dict['appId'] = self.appid
        param_dict['signa'] = self.signa
        param_dict['ts'] = self.ts
        param_dict["fileSize"] = file_len
        param_dict["fileName"] = file_name
        param_dict["duration"] = "0" # 设置为0让讯飞自动识别时长
        
        print("upload参数：", param_dict)
        data = open(upload_file_path, 'rb').read(file_len)

        response = requests.post(url =lfasr_host + api_upload+"?"+urllib.parse.urlencode(param_dict),
                                headers = {"Content-type":"application/json"},data=data)
        print("upload_url:",response.request.url)
        result = json.loads(response.text)
        print("upload resp:", result)
        
        if result['code'] != '000000':
            raise Exception(f"长语音上传失败: {result.get('descInfo', '未知错误')}")
        return result

    def get_result(self):
        try:
            uploadresp = self.upload()
            orderId = uploadresp['content']['orderId']
            
            param_dict = {}
            param_dict['appId'] = self.appid
            param_dict['signa'] = self.signa
            param_dict['ts'] = self.ts
            param_dict['orderId'] = orderId
            param_dict['resultType'] = "transfer,predict" # 包含转写和预测结果
            
            print("")
            print("长语音转写：查询部分：")
            print("get result参数：", param_dict)
            
            status = 3 # 初始状态为处理中
            max_retries = 30 # 最多查询30次 (5秒/次 * 30次 = 150秒 = 2.5分钟)
            retries = 0
            
            final_result = None # 用于存储最终的返回结果
            
            while status == 3 and retries < max_retries: # 只有状态为3时才继续轮询
                response = requests.post(url=lfasr_host + api_get_result + "?" + urllib.parse.urlencode(param_dict),
                                         headers={"Content-type": "application/json"})
                result = json.loads(response.text)
                print("get_result resp:", result) # 每次轮询都打印一次结果
                
                if result['code'] != '000000':
                    raise Exception(f"长语音查询失败: {result.get('descInfo', '未知错误')}")

                status = result['content']['orderInfo']['status']
                final_result = result # 保存当前结果

                if status == 4 or status == -1: # <--- 关键修改：当状态为4或-1时，都跳出循环
                    break
                
                retries += 1
                time.sleep(5) # 每5秒查询一次

            # 循环结束后，根据最终状态判断
            if final_result and (status == 4 or status == -1): # <--- 关键修改：检查最终状态是否为4或-1
                print(f"长语音转写完成，最终状态: {status}. 结果: {final_result}")
                return final_result
            else:
                raise Exception("长语音转写超时或未完成。")
                
        except Exception as e:
            print(f"长语音转写API调用失败: {e}")
            return {"code": "ERROR", "descInfo": str(e), "content": {"orderInfo": {"status": -99, "failType": 0}, "orderResult": ""}} # 返回一个包含错误信息的结构，避免后续代码崩溃

# =====================================================================================
# 4. 讯飞星火大模型 API 客户端
# =====================================================================================

class SparkLLMClient:
    def __init__(self, appid, api_key, api_secret, spark_url, domain):
        self.appid = appid
        self.api_key = api_key
        self.api_secret = api_secret
        self.spark_url = spark_url
        self.domain = domain
        self._full_response = ""
        self._is_finished = threading.Event() # 用于同步等待结果
        self._error_message = None
        self._ws = None # 存储 websocket 连接实例

    def _create_url(self):
        now = datetime.now()
        date = format_date_time(mktime(now.timetuple()))
        host = urllib.parse.urlparse(self.spark_url).netloc
        path = urllib.parse.urlparse(self.spark_url).path

        signature_origin = f"host: {host}\ndate: {date}\nGET {path} HTTP/1.1"
        signature_sha = hmac.new(self.api_secret.encode('utf-8'), signature_origin.encode('utf-8'), digestmod=hashlib.sha256).digest()
        signature_sha_base64 = base64.b64encode(signature_sha).decode(encoding='utf-8')
        authorization_origin = f'api_key="{self.api_key}", algorithm="hmac-sha256", headers="host date request-line", signature="{signature_sha_base64}"'
        authorization = base64.b64encode(authorization_origin.encode('utf-8')).decode(encoding='utf-8')

        v = {
            "authorization": authorization,
            "date": date,
            "host": host
        }
        return self.spark_url + '?' + urllib.parse.urlencode(v)

    def _gen_params(self, question_text_payload):
        # question_text_payload 应该是类似 [{"role": "user", "content": "..."}] 的结构
        data = {
            "header": {
                "app_id": self.appid,
                "uid": "interview_user",
            },
            "parameter": {
                "chat": {
                    "domain": self.domain,
                    "temperature": 0.7, # 适当降低温度，让结果更稳定
                    "max_tokens": 4096 # 根据模型版本调整最大token数
                }
            },
            "payload": {
                "message": {
                    "text": question_text_payload
                }
            }
        }
        return data

    def _on_message(self, ws, message):
        data = json.loads(message)
        code = data['header']['code']
        if code != 0:
            self._error_message = f'星火大模型请求错误: {code}, {data.get("header",{}).get("message", "未知错误")}'
            self._is_finished.set()
            return

        choices = data["payload"]["choices"]
        status = choices["status"]
        
        # 提取 content
        content_text = ""
        if 'text' in choices and len(choices['text']) > 0:
            content_text = choices['text'][0].get('content', '')
        
        self._full_response += content_text # 收集所有分块的文本

        if status == 2: # 收到结束标志
            self._is_finished.set() # 信号量置位，通知主线程可以读取结果了

    def _on_error(self, ws, error):
        self._error_message = f"星火大模型WebSocket错误: {error}"
        self._is_finished.set()

    def _on_close(self, ws, close_status_code, close_msg):
        # print("星火大模型WebSocket已关闭。")
        if not self._is_finished.is_set(): # 如果是意外关闭，也设置信号量
            self._error_message = "星火大模型WebSocket意外关闭。"
            self._is_finished.set()
            
    def get_json_response(self, prompt_text, timeout=60):
        """
        向星火大模型发送请求，并尝试解析返回的JSON字符串。
        用于生成问题等场景。
        """
        messages = [{"role": "user", "content": prompt_text}]
        json_str = self._run_websocket_request(messages, timeout)
        try:
            return json.loads(json_str)
        except json.JSONDecodeError as e:
            raise Exception(f"解析星火大模型返回的JSON失败: {e}. 原始文本: {json_str}")

    def get_evaluation(self, question_text, interview_questions_list):
        """
        向星火大模型发送请求，获取面试评估结果。
        question_text: 包含所有面试回答的完整转写文本。
        interview_questions_list: 面试官提出的所有问题列表，用于指导AI评估。
        """
        self._full_response = ""
        self._error_message = None
        self._is_finished.clear() # 重置信号量

        # 构建详细的Prompt
        questions_str = "\n".join([f"  - {q}" for q in interview_questions_list])
        prompt_content = f"""
        你是一名资深的HR面试官和AI评测专家。你的任务是根据候选人的完整面试回答文本，从多个维度对其进行专业评估。
        面试官提出的问题列表如下：
        {questions_str}

        以下是候选人的完整回答（语音转写文本）：
        ```
        {question_text}
        ```

        请你严格按照以下JSON格式返回评估结果。不要包含任何额外的文字、Markdown标记（如```json```）、或解释。
        
        {{
            "overall_score": <int, 0-100的综合评分>,
            "competencies": {{
                "专业知识水平": <int, 0-100评分>,
                "技能匹配度": <int, 0-100评分>,
                "语言表达能力": <int, 0-100评分>,
                "逻辑思维能力": <int, 0-100评分>,
                "创新能力": <int, 0-100评分>,
                "应变抗压能力": <int, 0-100评分>
            }},
            "summary_strengths": "<string, 总结候选人的主要优点，简洁明了>",
            "summary_weaknesses": "<string, 总结候选人的主要不足和可以改进的地方，简洁明了>",
            "specific_suggestions": [
                "<string, 具体到某个问题或某个方面的改进建议，例如：回答‘你为什么感兴趣’时缺乏具体案例，可以考虑使用STAR原则。",
                "<string, 另一条改进建议>"
            ],
            "radar_chart_data": {{
                "labels": ["专业知识水平", "技能匹配度", "语言表达能力", "逻辑思维能力", "创新能力", "应变抗压能力"],
                "values": [<int, 对应上述6项能力的评分>]
            }}
        }}
        """
        
        # 将Prompt包装成符合API要求的message.text格式
        question_payload = [
            {"role": "user", "content": prompt_content}
        ]
        
        request_data = self._gen_params(question_payload)

        ws_url = self._create_url()
        self._ws = websocket.WebSocketApp(ws_url, 
                                    on_message=self._on_message, 
                                    on_error=self._on_error, 
                                    on_close=self._on_close)
        
        # 将请求数据附加到 ws 对象，以便 on_open 能够发送
        self._ws._question_payload = request_data

        # 在新线程中运行 WebSocket 连接
        ws_thread = threading.Thread(target=lambda: self._ws.run_forever(sslopt={"cert_reqs": ssl.CERT_NONE}))
        ws_thread.daemon = True # 守护线程，主程序退出时自动结束
        ws_thread.start()

        # 等待连接建立并通过 run 发送初始数据
        time.sleep(1) # 等待连接建立
        if not self._error_message and self._ws.sock and self._ws.sock.connected: # 确保连接成功
            self._ws.send(json.dumps(self._ws._question_payload))
        else:
            raise Exception(f"无法建立星火大模型WebSocket连接: {self._error_message}")


        # 等待结果或超时
        if not self._is_finished.wait(timeout=120): # 120秒超时
            self._ws.close()
            self._error_message = "星火大模型请求超时。"
        
        # 关闭WebSocket连接
        self._ws.close()

        if self._error_message:
            raise Exception(self._error_message)
        
        try:
            # 尝试解析完整的JSON响应
            cleaned_json_str = self._full_response.strip().replace("```json\n", "").replace("```", "").strip()
            evaluation_result = json.loads(cleaned_json_str)
            return evaluation_result
        except json.JSONDecodeError as e:
            raise Exception(f"解析星火大模型返回的JSON失败: {e}. 原始文本: {self._full_response}")
        except Exception as e:
            raise Exception(f"处理星火大模型结果失败: {e}")
        
    def get_questions(self, resume_text):
        """
        向星火大模型发送请求，获取面试评估结果。
        question_text: 包含所有面试回答的完整转写文本。
        interview_questions_list: 面试官提出的所有问题列表，用于指导AI评估。
        """
        self._full_response = ""
        self._error_message = None
        self._is_finished.clear() # 重置信号量

        """使用大模型根据简历内容生成面试问题"""
        # 限制简历文本长度，避免超出大模型的token限制
        prompt_content = f"""你是一名专业的HR。根据以下简历内容，生成5个最能考察候选人能力和经历的面试问题。问题应与简历内容紧密相关，同时也可以包含一些通用的行为面试问题。
        请以JSON数组的格式返回这5个问题。不要包含任何额外的文字、解释或Markdown标记。例如：
        ["问题1", "问题2", "问题3", "问题4", "问题5"]
        简历内容：
        ```
        {resume_text}
        ```
        """
        
        # 将Prompt包装成符合API要求的message.text格式
        question_payload = [
            {"role": "user", "content": prompt_content}
        ]
        
        request_data = self._gen_params(question_payload)

        ws_url = self._create_url()
        self._ws = websocket.WebSocketApp(ws_url, 
                                    on_message=self._on_message, 
                                    on_error=self._on_error, 
                                    on_close=self._on_close)
        
        # 将请求数据附加到 ws 对象，以便 on_open 能够发送
        self._ws._question_payload = request_data

        # 在新线程中运行 WebSocket 连接
        ws_thread = threading.Thread(target=lambda: self._ws.run_forever(sslopt={"cert_reqs": ssl.CERT_NONE}))
        ws_thread.daemon = True # 守护线程，主程序退出时自动结束
        ws_thread.start()

        # 等待连接建立并通过 run 发送初始数据
        time.sleep(1) # 等待连接建立
        if not self._error_message and self._ws.sock and self._ws.sock.connected: # 确保连接成功
            self._ws.send(json.dumps(self._ws._question_payload))
        else:
            raise Exception(f"无法建立星火大模型WebSocket连接: {self._error_message}")


        # 等待结果或超时
        if not self._is_finished.wait(timeout=120): # 120秒超时
            self._ws.close()
            self._error_message = "星火大模型请求超时。"
        
        # 关闭WebSocket连接
        self._ws.close()

        if self._error_message:
            raise Exception(self._error_message)
        
        try:
            # 尝试解析完整的JSON响应
            cleaned_json_str = self._full_response.strip().replace("```json\n", "").replace("```", "").strip()
            evaluation_result = json.loads(cleaned_json_str)
            return evaluation_result
        except json.JSONDecodeError as e:
            raise Exception(f"解析星火大模型返回的JSON失败: {e}. 原始文本: {self._full_response}")
        except Exception as e:
            raise Exception(f"处理星火大模型结果失败: {e}")
        
def extract_text_from_pdf(pdf_path):
    """从PDF文件中提取文本"""
    try:
        text = extract_text(pdf_path)
        return text
    except Exception as e:
        print(f"从PDF提取文本失败: {e}")
        return None

# =====================================================================================
# 5. FLASK WEB 路由 (保持不变，或根据需求微调)
# =====================================================================================

@app.route('/')
def index():
    session.clear()
    return render_template('index.html')

@app.route('/upload_resume', methods=['POST'])
def upload_resume():
    """处理简历上传，提取文本，生成面试问题，并重定向到面试页面"""
    if 'resume_file' not in request.files:
        return jsonify({"status": "error", "message": "未找到简历文件。"}), 400

    resume_file = request.files['resume_file']
    if resume_file.filename == '':
        return jsonify({"status": "error", "message": "未选择文件。"}), 400

    if not resume_file.filename.lower().endswith('.pdf'):
        return jsonify({"status": "error", "message": "只支持PDF文件。"}), 400

    filename = secure_filename(resume_file.filename)
    temp_pdf_path = os.path.join(UPLOAD_TEMP_DIR, f"{int(time.time())}_{filename}")
    resume_file.save(temp_pdf_path)
    print(f"简历已临时保存到: {temp_pdf_path}")

    resume_text = None
    try:
        resume_text = extract_text_from_pdf(temp_pdf_path)
        if not resume_text or len(resume_text.strip()) < 50: 
            return jsonify({"status": "error", "message": "无法从PDF中提取有效文本，请确保PDF是文本格式而非扫描图片。"}), 500

        # 将简历文本保存为TXT文件
        resume_txt_filename = f"resume_{int(time.time())}.txt"
        resume_txt_filepath = os.path.join(ANSWERS_DIR, resume_txt_filename)
        with open(resume_txt_filepath, 'w', encoding='utf-8') as f:
            f.write(resume_text)
        print(f"简历文本已保存到: {resume_txt_filepath}")
        session['resume_txt_filepath'] = resume_txt_filepath # 存入session备用

        spark_llm_client_for_questions = SparkLLMClient(
            appid=SPARK_APPID,
            api_key=SPARK_API_KEY,
            api_secret=SPARK_API_SECRET,
            spark_url=SPARK_URL,
            domain=SPARK_DOMAIN
        )

        print("正在调用星火大模型进行简历解析提问...")
        generated_questions = spark_llm_client_for_questions.get_questions(resume_text)

        if generated_questions:
            session['generated_questions'] = generated_questions
            session['job_title'] = request.form.get('job_title', '通用岗位') 
            print("定制问题生成成功！")
            return jsonify({"status": "success", "message": "定制问题生成成功，正在跳转...", "redirect_url": url_for('interview')})
        else:
            session['generated_questions'] = [
                "你好，请先用30秒做个简单的自我介绍。",
                "你为什么对这个岗位感兴趣？",
                "谈谈你最大的一个优点和缺点。",
                "你对我们公司有什么了解吗？",
                "你有什么问题想问我们吗？"
            ]
            session['job_title'] = request.form.get('job_title', '通用岗位')
            print("未能生成定制问题，将使用通用问题。")
            return jsonify({"status": "warning", "message": "未能生成定制问题，将使用通用问题。", "redirect_url": url_for('interview')})

    except Exception as e:
        print(f"简历处理或问题生成失败: {e}")
        return jsonify({"status": "error", "message": f"简历处理失败: {e}"}), 500
    finally:
        if os.path.exists(temp_pdf_path):
            os.remove(temp_pdf_path)

@app.route('/interview')
def interview():
    job_title = request.args.get('job', '通用岗位')
    
    questions_to_use = session.get('generated_questions', [
        "你好，请先用30秒做个简单的自我介绍。",
        "你为什么对这个岗位感兴趣？",
        "谈谈你最大的一个优点和缺点。",
        "你对我们公司有什么了解吗？",
        "你有什么问题想问我们吗？"
    ])
    
    session['questions'] = questions_to_use
    
    # 将 job_title 和最终使用的问题列表传递给模板
    return render_template('interview.html', job_title=job_title, questions=questions_to_use)

@app.route('/result')
def result():
    recording_path = session.get('recording_path')
    job_title = session.get('job_title', '未知岗位')
    transcription_filepath = session.get('transcription_filepath')
    llm_evaluation = session.get('llm_evaluation') # 获取LLM评估结果

    transcribed_text = "未找到转写结果。"
    if transcription_filepath and os.path.exists(transcription_filepath):
        try:
            with open(transcription_filepath, 'r', encoding='utf-8') as f:
                transcribed_text = f.read()
        except Exception as e:
            transcribed_text = f"读取转写文件失败: {e}"
    
    if not recording_path:
        return redirect(url_for('index'))
        
    return render_template('result.html', 
                           recording_path=recording_path, 
                           job_title=job_title,
                           transcribed_text=transcribed_text,
                           llm_evaluation=llm_evaluation) # 传递LLM评估结果给模板

# =====================================================================================
# 6. 核心API路由 (重点修改这部分)
# =====================================================================================

@app.route('/api/upload_full_interview', methods=['POST'])
def upload_full_interview():
    """
    接收完整面试录音，转为MP3，调用长语音转写，再调用星火大模型进行评估。
    """
    if 'full_audio' not in request.files:
        return jsonify({"status": "error", "message": "未找到音频文件。"}), 400

    audio_file = request.files['full_audio']

    if audio_file:
        timestamp = int(time.time())
        job_title = session.get('job_title', 'interview').replace(" ", "_")
        
        original_filename = f"{job_title}_{timestamp}.webm"
        mp3_filename = f"{job_title}_{timestamp}.mp3"
        transcription_filename = f"{job_title}_{timestamp}.txt"
        llm_analysis_filename = f"{job_title}_{timestamp}_llm.json" # 大模型结果文件名

        original_filepath = os.path.join(RECORDINGS_DIR, original_filename)
        mp3_filepath = os.path.join(RECORDINGS_DIR, mp3_filename)
        transcription_filepath = os.path.join(ANSWERS_DIR, transcription_filename)
        llm_analysis_filepath = os.path.join(ANSWERS_DIR, llm_analysis_filename)
        
        full_transcribed_text = "转写失败或无内容。"
        llm_evaluation_result = {"status": "error", "message": "AI评估未执行或失败。"}

        try:
            # 1. 保存前端上传的原始文件 (webm格式)
            audio_file.save(original_filepath)
            print(f"原始录音文件已保存到: {original_filepath}")
            
            # 2. 将原始 WebM 转换为 MP3
            print(f"正在将 {original_filename} 转换为 MP3...")
            audio = AudioSegment.from_file(original_filepath, format="webm")
            audio.export(mp3_filepath, format="mp3", bitrate="128k") 
            print(f"MP3 文件已成功生成: {mp3_filepath}")

            # 3. 调用讯飞长语音转写API
            print("正在调用讯飞长语音转写API...")
            lfasr_api_client = LongAudioRequestApi(
                appid=LFASR_APPID,
                secret_key=LFASR_SECRET_KEY,
                upload_file_path=mp3_filepath
            )
            
            transcription_raw_result = lfasr_api_client.get_result()
            
            if transcription_raw_result and transcription_raw_result.get('code') == '000000':
                order_result_str = transcription_raw_result['content']['orderResult']
                order_result_json = json.loads(order_result_str)
                
                extracted_texts = []
                if 'lattice' in order_result_json:
                    for item in order_result_json['lattice']:
                        if 'json_1best' in item:
                            json_1best_data = json.loads(item['json_1best'])
                            if 'st' in json_1best_data and 'rt' in json_1best_data['st']:
                                for rt_item in json_1best_data['st']['rt']:
                                    if 'ws' in rt_item:
                                        for ws_item in rt_item['ws']:
                                            if 'cw' in ws_item:
                                                for cw_item in ws_item['cw']:
                                                    extracted_texts.append(cw_item.get('w', ''))
                
                if extracted_texts:
                    full_transcribed_text = "".join(extracted_texts).replace("。", "。\n") 
                else:
                    full_transcribed_text = "转写结果为空。"
                
                # 保存转写结果到 txt 文件
                with open(transcription_filepath, 'w', encoding='utf-8') as f:
                    f.write(full_transcribed_text)
                print(f"转写文本已保存到: {transcription_filepath}")

            else:
                print(f"讯飞长语音转写API返回错误或无结果: {transcription_raw_result}")
                full_transcribed_text = f"转写API错误: {transcription_raw_result.get('descInfo', '未知错误')}"

            # 4. 【核心集成】调用星火大模型进行评估
            if full_transcribed_text and not full_transcribed_text.startswith("转写失败"):
                print("正在调用星火大模型进行面试评估...")
                spark_llm_client = SparkLLMClient(
                    appid=SPARK_APPID,
                    api_key=SPARK_API_KEY,
                    api_secret=SPARK_API_SECRET,
                    spark_url=SPARK_URL,
                    domain=SPARK_DOMAIN
                )
                
                # 获取面试官所有问题列表，用于Prompt
                interview_questions = session.get('questions', []) 
                
                llm_evaluation_result = spark_llm_client.get_evaluation(full_transcribed_text, interview_questions)
                
                # 保存大模型分析结果到 JSON 文件
                with open(llm_analysis_filepath, 'w', encoding='utf-8') as f:
                    json.dump(llm_evaluation_result, f, indent=4, ensure_ascii=False)
                print(f"大模型分析结果已保存到: {llm_analysis_filepath}")

            else:
                llm_evaluation_result = {"status": "warning", "message": "无有效转写文本，跳过AI评估。"}
                print("无有效转写文本，跳过AI评估。")

        except Exception as e:
            print(f"音频处理或AI调用过程中发生异常: {e}")
            llm_evaluation_result = {"status": "error", "message": f"服务器处理异常: {e}"}
        finally:
            # 无论成功失败，将所有相关文件路径和结果存入session
            session['recording_path'] = mp3_filepath # MP3文件的路径
            session['transcription_filepath'] = transcription_filepath # 文本文件的路径
            session['llm_analysis_filepath'] = llm_analysis_filepath # 大模型结果文件路径
            session['llm_evaluation'] = llm_evaluation_result # 大模型评估结果（字典）

            # 可以选择删除原始的webm文件以节省空间
            os.remove(original_filepath) 

        # 5. 向前端返回成功信息
        return jsonify({
            "status": "success",
            "message": "面试录音和AI分析已处理完成，正在生成报告。",
            "redirect_url": url_for('result')
        })

    return jsonify({"status": "error", "message": "上传失败。"}), 500


# =====================================================================================
# 7. 启动应用
# =====================================================================================

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)