document.addEventListener('DOMContentLoaded', () => {
    const startBtn = document.getElementById('start-btn');
    const stopBtn = document.getElementById('stop-btn');
    const questionBox = document.getElementById('question-box');
    const statusEl = document.getElementById('status');
    const videoElement = document.getElementById('user-video');

    let recorder;
    let audioContext;
    let stream;
    let questionCounter = 0;
    let currentQuestion = '';
    let isUploading = false;

    const questions = [
        "你好，请先用30秒做个简单的自我介绍。",
        "你为什么对我们公司和这个岗位感兴趣？",
        "请分享一个你遇到的最大挑战以及你是如何解决的。",
        "你对未来3-5年有什么职业规划？",
        "最后，你有什么问题想问我们吗？"
    ];

    async function initMedia() {
        try {
            stream = await navigator.mediaDevices.getUserMedia({ audio: true, video: true });
            videoElement.srcObject = stream;

            audioContext = new (window.AudioContext || window.webkitAudioContext)();
            const input = audioContext.createMediaStreamSource(stream);

            recorder = new Recorder(input, { numChannels: 1 });

            statusEl.textContent = '状态：设备就绪，点击“开始提问”以开始面试。';
            startBtn.disabled = false;
        } catch (err) {
            console.error('媒体初始化失败:', err);
            statusEl.textContent = '错误：无法访问麦克风或摄像头，请检查权限设置。';
            startBtn.disabled = true;
        }
    }

    function startQuestion() {
        if (questionCounter >= questions.length || isUploading) return;

        currentQuestion = questions[questionCounter];
        questionBox.textContent = currentQuestion;

        recorder.clear();
        recorder.record();

        statusEl.textContent = `正在录制第 ${questionCounter + 1} 题，请开始作答...`;
        startBtn.textContent = '回答完毕';
        stopBtn.style.display = 'inline-block';
    }

    function stopQuestion() {
        recorder.stop();

        statusEl.textContent = '正在处理您的回答，请稍候...';
        startBtn.disabled = true;
        isUploading = true;

        recorder.exportWAV(blob => {
            uploadAudio(blob, currentQuestion);
        });
    }

    function endInterview() {
        statusEl.textContent = '面试结束，正在跳转到结果页面...';
        startBtn.disabled = true;
        stopBtn.disabled = true;

        setTimeout(() => {
            window.location.href = "/result";
        }, 3000);
    }

    function uploadAudio(blob, question) {
        const formData = new FormData();
        formData.append('audio', blob, 'interview.wav');
        formData.append('question', question);

        fetch('/api/process_answer', {
            method: 'POST',
            body: formData
        })
        .then(res => res.json())
        .then(data => {
            isUploading = false;
            startBtn.disabled = false;

            if (data.status === 'success') {
                statusEl.textContent = `第 ${questionCounter + 1} 题处理完成。`;
                questionCounter++;

                if (questionCounter >= questions.length) {
                    startBtn.textContent = '查看报告';
                } else {
                    startBtn.textContent = '下一题';
                }
            } else {
                statusEl.textContent = `识别失败：${data.message}`;
                startBtn.textContent = '重试本题';
            }
        })
        .catch(err => {
            console.error('上传失败:', err);
            statusEl.textContent = '上传失败，请检查网络连接。';
            isUploading = false;
            startBtn.disabled = false;
            startBtn.textContent = '重试本题';
        });
    }

    if (startBtn) {
        startBtn.disabled = true;
        initMedia();

        startBtn.addEventListener('click', () => {
            if (isUploading) return;

            if (questionCounter >= questions.length) {
                endInterview();
            } else if (recorder && recorder.recording) {
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
