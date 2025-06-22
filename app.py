import os
import time
import json
import threading
from flask import Flask, request, jsonify, render_template, session, redirect, url_for
from werkzeug.utils import secure_filename
from pydub import AudioSegment

from sst import transcribe_audio  # 使用你贴的 REST API 封装实现
from llm_client import generate_questions, evaluate_answer, generate_report

app = Flask(__name__)
app.secret_key = os.urandom(24)

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
AUDIO_DIR = os.path.join(BASE_DIR, "audio")

UPLOADS_DIR = "uploads"
ANSWER_DIR = "answer"
RESUME_DIR = "resumes"

for folder in [UPLOADS_DIR, AUDIO_DIR, ANSWER_DIR, RESUME_DIR]:
    os.makedirs(folder, exist_ok=True)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload_resume', methods=['POST'])
def upload_resume():
    file = request.files['resume']
    if file:
        filename = secure_filename(file.filename)
        save_path = os.path.join(RESUME_DIR, f"{time.time_ns()}_{filename}")
        file.save(save_path)
        session['resume_path'] = save_path
        return jsonify({"status": "success", "path": save_path})
    return jsonify({"status": "error", "message": "No file uploaded."})

@app.route('/start_interview', methods=['POST'])
def start_interview():
    job = request.form.get('job', '通用岗位')
    session['job_title'] = job
    resume_path = session.get('resume_path', None)

    resume_text = ""
    if resume_path and os.path.exists(resume_path):
        with open(resume_path, 'r', encoding='utf-8', errors='ignore') as f:
            resume_text = f.read()

    questions = generate_questions(resume_text, job)
    session['questions'] = questions
    session['results'] = []
    session['current_q'] = 0
    return redirect(url_for('interview'))

@app.route('/interview')
def interview():
    return render_template('interview.html')

@app.route('/get_next_question')
def get_next_question():
    idx = session.get('current_q', 0)
    questions = session.get('questions', [])
    if idx >= len(questions):
        return jsonify({"status": "done"})
    return jsonify({"status": "ok", "question": questions[idx]})

@app.route('/api/process_answer', methods=['POST'])
def process_answer():
    if 'audio' not in request.files:
        return jsonify({"status": "error", "message": "No audio uploaded."})

    audio_file = request.files['audio']
    question = request.form.get('question', '未知问题')

    ts = time.time_ns()
    raw_path = os.path.join(AUDIO_DIR, f"{ts}_{secure_filename(audio_file.filename)}")
    pcm_path = os.path.join(AUDIO_DIR, f"{ts}.pcm")

    audio_file.save(raw_path)
    print(f"保存原始音频路径：{raw_path}")

    try:
        audio = AudioSegment.from_file(raw_path)
        audio = audio.set_frame_rate(16000).set_channels(1).set_sample_width(2)
        audio.export(pcm_path, format="s16le")
        print(f"保存转换音频路径：{pcm_path}")
    except Exception as e:
        return jsonify({"status": "error", "message": f"音频转换失败: {e}"})

    text = transcribe_audio(pcm_path)
    
@app.route('/result')
def result():
    results = session.get('results', [])
    summary = generate_report(results)
    return render_template('final_report.html', results=results, summary=summary)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)
