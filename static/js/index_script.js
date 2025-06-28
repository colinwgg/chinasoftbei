document.addEventListener('DOMContentLoaded', () => {
    const uploadForm = document.getElementById('resume-upload-form');
    const uploadStatusEl = document.getElementById('upload-status');
    const uploadBtn = document.getElementById('upload-resume-btn');

    if (uploadForm) {
        uploadForm.addEventListener('submit', async (e) => {
            e.preventDefault(); // 阻止表单默认提交行为

            uploadStatusEl.textContent = '状态：正在上传简历并生成问题，这可能需要一些时间...';
            uploadBtn.disabled = true; // 禁用按钮防止重复提交
            uploadBtn.style.opacity = 0.7; // 视觉反馈

            const formData = new FormData(uploadForm); // 从表单构建 FormData 对象
            
            try {
                const response = await fetch('/upload_resume', {
                    method: 'POST',
                    body: formData
                });
                const data = await response.json(); // 解析JSON响应

                if (response.ok && (data.status === 'success' || data.status === 'warning')) {
                    uploadStatusEl.textContent = data.message + ' 正在跳转到面试页面...';
                    window.location.href = data.redirect_url; // 跳转到面试页面
                } else {
                    // 处理非2xx状态码或后端返回的错误状态
                    uploadStatusEl.textContent = `错误: ${data.message || '未知错误'}`;
                }
            } catch (error) {
                console.error('简历上传或问题生成失败:', error);
                uploadStatusEl.textContent = `上传或问题生成失败: ${error.message}`;
            } finally {
                uploadBtn.disabled = false; // 恢复按钮
                uploadBtn.style.opacity = 1;
            }
        });
    }
});