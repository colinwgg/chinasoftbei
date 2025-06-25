import os
import time
import json
import base64
import hashlib
import hmac
import requests # 新增导入
import urllib.parse # 新增导入

from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from pydub import AudioSegment # 确保已安装 pydub

# =====================================================================================
# 1. FLASK 应用设置
# =====================================================================================

app = Flask(__name__)
app.secret_key = 'a_different_secret_key_for_this_approach'

# 定义录音文件和转写结果文件的存储目录
RECORDINGS_DIR = 'static/recordings' # 录音文件存放处
ANSWERS_DIR = 'answers' # 转写结果文本文件存放处

if not os.path.exists(RECORDINGS_DIR):
    os.makedirs(RECORDINGS_DIR)
if not os.path.exists(ANSWERS_DIR):
    os.makedirs(ANSWERS_DIR)

# =====================================================================================
# 2. 讯飞长语音转写 API 配置 (从您提供的模板复制)
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
        # duration 参数根据文档是可选的，如果知道时长可以提供，不知道则省略
        # 这里设置为 '0' 允许讯飞自动识别时长
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

    # 在 app.py 中找到 LongAudioRequestApi 类的 get_result 函数并替换它

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
# 3. FLASK WEB 路由
# =====================================================================================

@app.route('/')
def index():
    session.clear() # 清空会话，确保每次从首页开始都是全新的
    return render_template('index.html')

@app.route('/interview')
def interview():
    job_title = request.args.get('job', '通用岗位')
    session['questions'] = [
        "你好，请先用30秒做个简单的自我介绍。",
        "你为什么对这个岗位感兴趣？",
        "谈谈你最大的一个优点和缺点。",
        "你对我们公司有什么了解吗？",
        "你有什么问题想问我们吗？"
    ]
    session['job_title'] = job_title
    # 在 render_template 中传入 questions 变量
    return render_template('interview.html', job_title=job_title, questions=session['questions'])

@app.route('/result')
def result():
    # 从会话中获取这次面试保存的信息
    recording_path = session.get('recording_path')
    job_title = session.get('job_title', '未知岗位')
    transcription_filepath = session.get('transcription_filepath') # 获取转写文件路径

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
                           transcribed_text=transcribed_text)


# =====================================================================================
# 4. 核心API路由 (重点修改这部分)
# =====================================================================================

@app.route('/api/upload_full_interview', methods=['POST'])
def upload_full_interview():
    """
    核心API接口，接收并保存在面试结束后上传的完整录音。
    现在它会同时保存原始文件、转换MP3，并调用讯飞长语音转写API。
    """
    # 讯飞长语音转写API的APPID和SECRET_KEY
    # 请确保这些是为长语音服务申请的！可能与星火大模型不同。
    LFASR_APPID = os.environ.get("LFASR_APPID", "777b23bb")
    LFASR_SECRET_KEY = os.environ.get("LFASR_SECRET_KEY", "b1f7053fc49faebf828a76f317423cd7")

    if 'full_audio' not in request.files:
        return jsonify({"status": "error", "message": "未找到音频文件。"}), 400

    audio_file = request.files['full_audio']

    if audio_file:
        timestamp = int(time.time())
        job_title = session.get('job_title', 'interview').replace(" ", "_")
        
        original_filename = f"{job_title}_{timestamp}.webm"
        mp3_filename = f"{job_title}_{timestamp}.mp3"
        transcription_filename = f"{job_title}_{timestamp}.txt" # 转写结果的文件名

        original_filepath = os.path.join(RECORDINGS_DIR, original_filename)
        mp3_filepath = os.path.join(RECORDINGS_DIR, mp3_filename)
        transcription_filepath = os.path.join(ANSWERS_DIR, transcription_filename) # 转写结果的完整路径
        
        # 1. 保存前端上传的原始文件 (webm格式)
        audio_file.save(original_filepath)
        print(f"原始录音文件已保存到: {original_filepath}")
        
        # 2. 将原始 WebM 转换为 MP3
        try:
            print(f"正在将 {original_filename} 转换为 MP3...")
            audio = AudioSegment.from_file(original_filepath, format="webm")
            # 讯飞长语音转写支持多种音频格式，MP3是其中之一，但推荐PCM（WAV）
            # 这里为了满足您的“录制MP3”需求，我们仍转为MP3
            audio.export(mp3_filepath, format="mp3", bitrate="128k") 
            print(f"MP3 文件已成功生成: {mp3_filepath}")

            # 3. 【核心集成】调用讯飞长语音转写API
            print("正在调用讯飞长语音转写API...")
            api_client = LongAudioRequestApi(
                appid=LFASR_APPID,
                secret_key=LFASR_SECRET_KEY,
                upload_file_path=mp3_filepath # 使用MP3文件进行转写
            )
            
            transcription_result = api_client.get_result()
            
            full_transcribed_text = "未识别到文本或转写失败。"

            if transcription_result and transcription_result.get('code') == '000000':
                # 解析转写结果
                order_result_str = transcription_result['content']['orderResult']
                order_result_json = json.loads(order_result_str)
                
                # 提取转写文本
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
                    full_transcribed_text = "".join(extracted_texts).replace("。", "。\n") # 简单格式化
                
                print(f"转写成功，文本长度: {len(full_transcribed_text)}")

                # 4. 保存转写结果到 txt 文件
                with open(transcription_filepath, 'w', encoding='utf-8') as f:
                    f.write(full_transcribed_text)
                print(f"转写文本已保存到: {transcription_filepath}")

            else:
                print(f"讯飞长语音转写API返回错误或无结果: {transcription_result}")
                full_transcribed_text = f"转写API错误: {transcription_result.get('descInfo', '未知错误')}"

        except Exception as e:
            print(f"音频处理或转写过程中发生异常: {e}")
            full_transcribed_text = f"转写处理异常: {e}"
        finally:
            # 无论成功失败，将MP3文件路径和转写文本文件路径存入session
            session['recording_path'] = mp3_filepath # MP3文件的路径
            session['transcription_filepath'] = transcription_filepath # 文本文件的路径
            # 可以在这里选择是否删除原始的webm文件
            # os.remove(original_filepath) 

        # 5. 向前端返回成功信息
        return jsonify({
            "status": "success",
            "message": "面试录音已处理完成，正在生成报告。",
            "redirect_url": url_for('result')
        })

    return jsonify({"status": "error", "message": "上传失败。"}), 500


# =====================================================================================
# 5. 启动应用
# =====================================================================================

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)