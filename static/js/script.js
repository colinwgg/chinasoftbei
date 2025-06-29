document.addEventListener('DOMContentLoaded', () => {
    // 获取页面元素
    const videoElement = document.getElementById('user-video');
    const startBtn = document.getElementById('start-btn');
    const stopBtn = document.getElementById('stop-btn');
    const questionBox = document.getElementById('question-box');
    const statusEl = document.getElementById('status');
    const videoPlaceholder = document.querySelector('.video-placeholder'); // 获取占位符元素

    let mediaRecorder;
    let recordedChunks = [];
    let questionCounter = 0;

    const questionsElement = document.getElementById('questions-data');
    const questions = JSON.parse(questionsElement.textContent);

    // 初始化摄像头和麦克风
    async function initMedia() {
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: true });

            videoElement.srcObject = stream;

            videoElement.style.display = 'block';
            videoPlaceholder.style.display = 'none';

            mediaRecorder = new MediaRecorder(stream);

            mediaRecorder.ondataavailable = event => {
                if (event.data.size > 0) {
                    recordedChunks.push(event.data);
                }
            };

            mediaRecorder.onstop = () => {
                const fullBlob = new Blob(recordedChunks, { type: 'audio/mp3' });
                uploadFullRecording(fullBlob);
            };

            statusEl.textContent = '状态：设备就绪，点击“开始面试”以提问并开始录制。';
            startBtn.disabled = false;
        } catch (error) {
            statusEl.textContent = '错误：无法访问摄像头或麦克风，请检查浏览器权限。';
            console.error('getUserMedia 错误:', error);
        }
    }

    // “开始面试/下一题”按钮的逻辑
    function handleQuestionFlow() {
        if (mediaRecorder.state !== 'recording') {
            recordedChunks = [];
            mediaRecorder.start();
            statusEl.textContent = '录制已开始...';
            startBtn.textContent = '下一题';
            stopBtn.style.display = 'inline-block';
        }

        if (questionCounter < questions.length) {
            questionBox.textContent = questions[questionCounter];
            questionCounter++;
        }

        if (questionCounter >= questions.length) {
            startBtn.textContent = '所有问题已问完';
            startBtn.disabled = true;
            statusEl.textContent = '所有问题已问完，请点击“结束面试”以完成并上传录音。';
        }
    }
    
    // 结束面试并停止录制
    function finishInterview() {
        if (mediaRecorder && mediaRecorder.state === 'recording') {
            statusEl.textContent = '正在处理并上传完整录音，请稍候...';
            startBtn.disabled = true;
            stopBtn.disabled = true;
            mediaRecorder.stop();
        }
    }

    // 上传完整的录音文件
    function uploadFullRecording(blob) {
        const formData = new FormData();
        formData.append('full_audio', blob, 'full_interview.mp3');

        fetch('/api/upload_full_interview', {
            method: 'POST',
            body: formData
        })
        .then(response => response.json())
        .then(data => {
            if (data.status === 'success') {
                statusEl.textContent = '上传成功！正在跳转到结果页面...';
                window.location.href = data.redirect_url;
            } else {
                statusEl.textContent = `上传失败: ${data.message}`;
                startBtn.disabled = false;
                stopBtn.disabled = false;
            }
        })
        .catch(error => {
            console.error('上传失败:', error);
            statusEl.textContent = '上传失败，请检查网络连接。';
        });
    }

    // --- 事件绑定 ---
    initMedia();

    if (startBtn) {
        startBtn.textContent = '开始面试';
        startBtn.addEventListener('click', handleQuestionFlow);
    }

    if (stopBtn) {
        stopBtn.style.display = 'none';
        stopBtn.addEventListener('click', finishInterview);
    }
});