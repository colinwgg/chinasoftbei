// 这是全新的 script.js，请用它替换掉旧的JS文件内容
document.addEventListener('DOMContentLoaded', () => {
    // 获取页面元素
    const startBtn = document.getElementById('start-btn');
    const stopBtn = document.getElementById('stop-btn');
    const questionBox = document.getElementById('question-box');
    const statusEl = document.getElementById('status');
    const videoElement = document.getElementById('user-video');

    let mediaRecorder;
    let audioChunks = [];
    let questionCounter = 0;
    let currentQuestion = '';
    let isUploading = false;

    // 面试问题库
    const questions = [
        "你好，请先用30秒做个简单的自我介绍。",
        "你为什么对我们公司和这个岗位感兴趣？",
        "请分享一个你遇到的最大挑战以及你是如何解决的。",
        "你对未来3-5年有什么职业规划？",
        "最后，你有什么问题想问我们吗？"
    ];

    // 初始化摄像头和麦克风
    async function initMedia() {
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: true });
            videoElement.srcObject = stream;
            
            // 创建录制器，只录制音频
            mediaRecorder = new MediaRecorder(stream);

            // 当有音频数据可用时，存入数组
            mediaRecorder.ondataavailable = event => {
                audioChunks.push(event.data);
            };

            // 当录制停止时，将收集到的音频数据打包并上传
            mediaRecorder.onstop = () => {
                const audioBlob = new Blob(audioChunks, { type: 'audio/webm' });
                audioChunks = []; // 清空，为下一次录制做准备
                uploadAudio(audioBlob, currentQuestion);
            };

            statusEl.textContent = '状态：设备就绪，点击“开始提问”以开始面试。';
            startBtn.disabled = false;
        } catch (error) {
            statusEl.textContent = '错误：无法访问摄像头或麦克风，请检查浏览器权限。';
            console.error('getUserMedia 错误:', error);
            startBtn.disabled = true;
        }
    }

    // 开始提问并录制
    function startQuestion() {
        if (questionCounter >= questions.length || isUploading) return;
        
        isUploading = false;
        currentQuestion = questions[questionCounter];
        questionBox.textContent = currentQuestion;
        
        audioChunks = [];
        mediaRecorder.start();
        
        statusEl.textContent = `正在回答第 ${questionCounter + 1} 题...（录音中）`;
        startBtn.textContent = '回答完毕';
        stopBtn.style.display = 'inline-block'; // 显示结束面试按钮
    }

    // 停止录制
    function stopQuestion() {
        if (mediaRecorder && mediaRecorder.state === 'recording') {
            mediaRecorder.stop();
            isUploading = true;
            statusEl.textContent = '正在处理您的回答，请耐心等待...';
            startBtn.disabled = true; // 上传期间禁用按钮
        }
    }

    // 结束整个面试
    function endInterview() {
        statusEl.textContent = '面试结束！正在跳转到报告页面...';
        questionBox.textContent = "所有问题已回答完毕！";
        startBtn.disabled = true;
        stopBtn.disabled = true;
        if (mediaRecorder && mediaRecorder.state === 'recording') {
            mediaRecorder.stop(); // 确保最后的录音也被处理
        }
        
        // 等待一段时间，确保最后的上传和处理完成
        setTimeout(() => {
            window.location.href = '/result';
        }, 3000); 
    }

    // 上传音频文件到后端
    function uploadAudio(blob, question) {
        const formData = new FormData();
        formData.append('audio', blob, 'interview_answer.webm'); // 后端会处理格式，文件名不重要
        formData.append('question', question);

        fetch('/api/process_answer', {
            method: 'POST',
            body: formData
        })
        .then(response => {
            if (!response.ok) {
                throw new Error(`服务器错误: ${response.statusText}`);
            }
            return response.json();
        })
        .then(data => {
            isUploading = false;
            startBtn.disabled = false;
            if (data.status === 'success') {
                statusEl.textContent = `第 ${questionCounter + 1} 题评估完成。点击按钮继续。`;
                questionCounter++; // 只有成功后才增加题目计数
                if (questionCounter >= questions.length) {
                    startBtn.textContent = '查看最终报告';
                } else {
                    startBtn.textContent = '下一题';
                }
            } else {
                statusEl.textContent = `处理失败: ${data.message}，请重试。`;
                startBtn.textContent = '重试本题';
            }
        })
        .catch(error => {
            console.error('上传失败:', error);
            isUploading = false;
            startBtn.disabled = false;
            statusEl.textContent = `上传失败，请检查网络并重试。`;
            startBtn.textContent = '重试本题';
        });
    }

    // 绑定按钮事件
    if (startBtn) {
        startBtn.disabled = true; // 初始禁用，直到媒体加载完成
        initMedia(); // 页面加载时即初始化媒体

        startBtn.addEventListener('click', () => {
            if (isUploading) return;

            // 如果已经是最后一题之后
            if (questionCounter >= questions.length) {
                endInterview();
                return;
            }
            
            // 根据录制状态决定是开始还是停止
            if (mediaRecorder && mediaRecorder.state === 'recording') {
                stopQuestion();
            } else {
                startQuestion();
            }
        });
    }

    if (stopBtn) {
        stopBtn.addEventListener('click', endInterview);
    }
});