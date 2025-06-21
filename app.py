from flask import Flask, render_template, request, jsonify

app = Flask(__name__)

# 首页：选择面试岗位
@app.route('/')
def index():
    """渲染首页，提供岗位选择。"""
    return render_template('index.html')

# 面试页面：根据选择的岗位进行面试
@app.route('/interview')
def interview():
    """渲染面试页面。"""
    job_title = request.args.get('job', '通用岗位') # 从URL获取岗位名称
    return render_template('interview.html', job_title=job_title)

# 结果页面：展示面试评估报告
@app.route('/result')
def result():
    """渲染结果展示页面。"""
    # 在真实应用中，这里会从数据库或会话中获取评估数据
    # 这里我们使用静态数据作为示例
    evaluation_data = {
        "overall_score": 85,
        "clarity_score": 90,
        "relevance_score": 88,
        "confidence_score": 80,
        "suggestions": [
            "回答可以更具体一些，多用数据和实例支撑。",
            "在回答项目经验时，可以更突出个人贡献。",
            "注意保持与摄像头的眼神交流。"
        ],
        "transcript": "面试官：您好，请做个自我介绍。\n应聘者：我叫张三，我毕业于..." # 这里应该是真实的对话记录
    }
    return render_template('result.html', data=evaluation_data)

# API端点：处理面试数据
@app.route('/api/process_interview', methods=['POST'])
def process_interview_data():
    """
    接收前端发送的面试数据（如视频、音频流）。
    这是与AI模型交互的核心后端逻辑。
    """
    # -------------------------------------------------------------
    # 在这里添加调用讯飞星火大模型进行多模态评测的核心代码
    # 1. 接收前端发送的音频/视频数据
    # 2. 将数据发送到讯飞的API
    # 3. 接收讯飞返回的评测结果
    # 4. 处理结果并存储，然后重定向到结果页面
    # -------------------------------------------------------------

    # 这是一个示例返回值，表示接收成功
    print("接收到前端数据:", request.json)
    return jsonify({
        "status": "success",
        "message": "数据处理中，请稍后查看结果。",
        # 通常处理完后，前端会重定向到结果页面
        "result_url": "/result"
    })

if __name__ == '__main__':
    # 使用 0.0.0.0 使其可以被局域网访问，方便手机测试
    app.run(host='0.0.0.0', port=5001, debug=True)