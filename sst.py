# ===============================
# stt_lfasr.py - 语音识别模块（基于你提供的 REST 接口封装）
# ===============================
import base64
import hashlib
import hmac
import json
import os
import time
import requests
import urllib

lfasr_host = 'https://raasr.xfyun.cn/v2/api'
upload_endpoint = '/upload'
get_result_endpoint = '/getResult'

APPID = "777b23bb"
SECRET_KEY = "b1f7053fc49faebf828a76f317423cd7"


def transcribe_audio(file_path):
    ts = str(int(time.time()))
    m2 = hashlib.md5()
    m2.update((APPID + ts).encode('utf-8'))
    md5 = m2.hexdigest()
    signa = hmac.new(SECRET_KEY.encode('utf-8'), md5.encode('utf-8'), hashlib.sha1).digest()
    signa = base64.b64encode(signa).decode('utf-8')

    # Upload audio
    file_len = os.path.getsize(file_path)
    file_name = os.path.basename(file_path)
    params = {
        'appId': APPID,
        'signa': signa,
        'ts': ts,
        'fileSize': file_len,
        'fileName': file_name,
        'duration': '200'
    }

    with open(file_path, 'rb') as f:
        data = f.read()

    resp = requests.post(url=lfasr_host + upload_endpoint + '?' + urllib.parse.urlencode(params),
                         headers={'Content-type': 'application/json'},
                         data=data)
    res_json = resp.json()
    if res_json.get('code') != 0:
        return "[音频上传失败]"

    order_id = res_json['content']['orderId']

    # Poll result
    params['orderId'] = order_id
    params['resultType'] = 'transfer'
    status = 3
    for _ in range(20):
        time.sleep(5)
        resp = requests.post(url=lfasr_host + get_result_endpoint + '?' + urllib.parse.urlencode(params),
                             headers={'Content-type': 'application/json'})
        result = resp.json()
        status = result['content']['orderInfo']['status']
        if status == 4:
            return result['content']['orderResult']
    return "[识别超时]"