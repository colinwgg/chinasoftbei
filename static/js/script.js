document.addEventListener('DOMContentLoaded', () => {
    // 获取页面上的元素
    const videoElement = document.getElementById('user-video');
    const videoPlaceholder = document.querySelector('.video-placeholder');
    const startBtn = document.getElementById('start-btn');
    const stopBtn = document.getElementById('stop-btn');
    const questionBox = document.getElementById('question-box');
    const statusEl = document.getElementById('status');

    let mediaRecorder;
    let recordedChunks = [];
    let questionCounter = 0;

    // 模拟的面试问题库
    const questions = [
        "你好，请先用30秒做个简单的自我介绍。",
        "你为什么对这个岗位感兴趣？",
        "谈谈你最大的一个优点和缺点。",
        "你对我们公司有什么了解吗？",
        "你有什么问题想问我们吗？"
    ];

    // 请求摄像头和麦克风权限
    const initMedia = async () => {
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: true });
            videoElement.srcObject = stream;
            videoElement.style.display = 'block';
            videoPlaceholder.style.display = 'none';
            statusEl.textContent = '状态：设备准备就绪，请点击“开始/下一题”开始回答。';

            // 设置媒体录制器
            mediaRecorder = new MediaRecorder(stream);
            mediaRecorder.ondataavailable = (event) => {
                if (event.data.size > 0) {
                    recordedChunks.push(event.data);
                }
            };

            mediaRecorder.onstop = () => {
                // 当录制停止，整合数据并发送到后端
                const blob = new Blob(recordedChunks, { type: 'video/webm' });
                recordedChunks = []; // 清空缓存
                sendDataToServer(blob);
            };

        } catch (error) {
            console.error('获取媒体设备失败:', error);
            statusEl.textContent = '错误：无法访问摄像头或麦克风。请检查权限设置。';
            alert('无法访问摄像头或麦克风，请检查您的浏览器权限设置。');
        }
    };

    // 开始/下一题 按钮逻辑
    if (startBtn) {
        startBtn.addEventListener('click', () => {
            if (!mediaRecorder) {
                initMedia(); // 首次点击时初始化媒体
                return;
            }

            if (questionCounter < questions.length) {
                if (mediaRecorder.state === 'recording') {
                    mediaRecorder.stop(); // 停止上一题的录制
                }
                questionBox.textContent = questions[questionCounter];
                recordedChunks = []; // 清空旧数据
                mediaRecorder.start(); // 开始录制当前问题的回答
                statusEl.textContent = `状态：正在回答第 ${questionCounter + 1} 题，录制中...`;
                questionCounter++;
                startBtn.textContent = "回答完毕/下一题";
            } else {
                // 所有问题回答完毕
                if (mediaRecorder.state === 'recording') {
                    mediaRecorder.stop();
                }
                questionBox.textContent = "所有问题已回答完毕！正在处理您的面试数据...";
                statusEl.textContent = "状态：面试结束，正在生成报告。";
                startBtn.disabled = true;
                stopBtn.textContent = "查看报告";
            }
        });
    }

    // 结束面试 按钮逻辑
    if (stopBtn) {
        stopBtn.addEventListener('click', () => {
            if (mediaRecorder && mediaRecorder.state === 'recording') {
                mediaRecorder.stop();
            }
            // 停止视频流
            if (videoElement.srcObject) {
                videoElement.srcObject.getTracks().forEach(track => track.stop());
            }
            statusEl.textContent = "状态：面试已手动结束。";
            questionBox.textContent = "面试已结束。";
            
            // 如果是查看报告
            if(stopBtn.textContent === "查看报告" || recordedChunks.length > 0) {
                // 模拟处理时间后跳转
                setTimeout(() => {
                    window.location.href = '/result';
                }, 2000);
            } else {
                // 如果是中途直接结束，跳转到首页
                window.location.href = '/';
            }
        });
    }

    // 发送数据到服务器的函数 (目前是占位符)
    const sendDataToServer = (blob) => {
        console.log("正在准备发送数据...", blob);

        // 在真实应用中，你会使用 fetch API 发送数据
        // const formData = new FormData();
        // formData.append('video', blob, 'interview.webm');

        fetch('/api/process_interview', {
            method: 'POST',
            // 注意：直接发送Blob需要设置正确的Content-Type，或者使用FormData
            // 这里为了简单，我们只发送一个JSON消息作为示例
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ message: "A new recording is ready." }),
        })
        .then(response => response.json())
        .then(data => {
            console.log('后端响应:', data);
            statusEl.textContent = `状态：第 ${questionCounter} 题回答已上传。请点击“下一题”。`;
        })
        .catch(error => {
            console.error('上传失败:', error);
            statusEl.textContent = `状态：上传失败，请检查网络连接。`;
        });
    };
});