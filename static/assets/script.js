// 声明全局变量
let currentFiles = [];
let chatHistory = [];
let currentChatId = null;
let isProcessing = false;

// 等待DOM加载完成
document.addEventListener('DOMContentLoaded', function() {
    console.log('DOM Content Loaded');
    
    // 获取DOM元素
    const chatBox = document.getElementById('chat-box');
    const inputBox = document.getElementById('input-box');
    const sendButton = document.getElementById('send-button');
    const fileInput = document.getElementById('file-input');
    
    // 检查元素是否存在
    if (!chatBox) console.error('找不到chat-box元素');
    if (!inputBox) console.error('找不到input-box元素');
    if (!sendButton) console.error('找不到send-button元素');
    if (!fileInput) console.error('找不到file-input元素');
    
    // 绑定发送按钮点击事件
    if (sendButton) {
        console.log('绑定发送按钮事件');
        sendButton.addEventListener('click', function() {
            if (!isProcessing) {
                console.log('发送按钮被点击');
                handleSendMessage();
            }
        });
    }
    
    // 绑定输入框回车事件
    if (inputBox) {
        console.log('绑定输入框事件');
        inputBox.addEventListener('keydown', function(event) {
            if (event.key === 'Enter' && !event.shiftKey && !isProcessing) {
                console.log('检测到回车键');
                event.preventDefault();
                handleSendMessage();
            }
        });
        
        // 自动调整输入框高度
        inputBox.addEventListener('input', function() {
            this.style.height = 'auto';
            this.style.height = (this.scrollHeight) + 'px';
        });
    }
    
    // 更新历史记录
    updateHistoryList();
});

// 设置发送按钮状态
function setButtonState(isLoading) {
    const sendButton = document.getElementById('send-button');
    const sendIcon = sendButton.querySelector('.send-icon');
    const loadingIcon = sendButton.querySelector('.loading-icon');
    
    if (isLoading) {
        sendIcon.style.display = 'none';
        loadingIcon.style.display = 'block';
        sendButton.disabled = true;
    } else {
        sendIcon.style.display = 'block';
        loadingIcon.style.display = 'none';
        sendButton.disabled = false;
    }
}

// 创建消息元素
function createMessageElement(role, content) {
    console.log('创建消息元素:', role);
    
    // 创建消息容器
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${role}-message`;
    
    // 创建头像容器
    const avatarContainer = document.createElement('div');
    avatarContainer.className = 'avatar-container';
    
    // 创建头像图片
    const avatar = document.createElement('img');
    avatar.className = 'avatar';
    
    // 检查并加载头像
    const baseUrl = window.location.origin;
    const avatarPath = role === 'user' ? 'static/picture/user.jpg' : 'static/picture/LLM.png';
    const fullPath = `${baseUrl}/${avatarPath}`;
    
    console.log('尝试加载头像:', fullPath);
    
    // 测试头像是否可访问
    fetch(fullPath)
        .then(response => {
            if (!response.ok) {
                throw new Error(`头像加载失败: ${response.status} ${response.statusText}`);
            }
            console.log('头像可以访问:', fullPath);
        })
        .catch(error => {
            console.error('头像访问错误:', error);
        });
    
    avatar.src = fullPath;
    avatar.alt = role === 'user' ? '用户头像' : 'AI头像';
    
    // 添加加载事件监听
    avatar.onload = function() {
        console.log('头像加载成功:', fullPath);
    };
    
    avatar.onerror = function(error) {
        console.error('头像加载失败:', fullPath, error);
        // 使用备用头像
        this.src = role === 'user' ? 
            'data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><circle cx="12" cy="12" r="12" fill="%2310a37f"/></svg>' : 
            'data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><circle cx="12" cy="12" r="12" fill="%23098aa0"/></svg>';
    };
    
    avatarContainer.appendChild(avatar);
    
    // 创建消息内容
    const contentDiv = document.createElement('div');
    contentDiv.className = 'message-content';
    contentDiv.innerHTML = content.replace(/\n/g, '<br>');
    
    // 组装消息元素
    messageDiv.appendChild(avatarContainer);
    messageDiv.appendChild(contentDiv);
    
    return messageDiv;
}

// 处理发送消息
async function handleSendMessage() {
    console.log('开始处理发送消息');
    
    const inputBox = document.getElementById('input-box');
    const fileInput = document.getElementById('file-input');
    const chatBox = document.getElementById('chat-box');
    
    if (!inputBox || !fileInput || !chatBox) {
        console.error('无法获取必要的DOM元素');
        return;
    }
    
    const message = inputBox.value.trim();
    const files = fileInput.files;
    
    console.log('消息内容:', message);
    console.log('文件数量:', files.length);
    
    if (!message && files.length === 0) {
        console.log('没有消息和文件，不发送请求');
        return;
    }
    
    if (isProcessing) {
        console.log('消息正在处理中，忽略新的请求');
        return;
    }
    
    try {
        isProcessing = true;
        setButtonState(true);
        inputBox.disabled = true;
        
        // 添加用户消息到聊天框
        const userMessageElement = createMessageElement('user', message);
        if (files.length > 0) {
            const fileInfo = document.createElement('div');
            fileInfo.className = 'file-info';
            fileInfo.innerHTML = Array.from(files).map(file => file.name).join('<br>');
            userMessageElement.querySelector('.message-content').appendChild(fileInfo);
        }
        chatBox.appendChild(userMessageElement);
        chatBox.scrollTop = chatBox.scrollHeight;
        
        // 添加AI消息框
        const aiMessageElement = createMessageElement('ai', '');
        const aiMessageContent = aiMessageElement.querySelector('.message-content');
        chatBox.appendChild(aiMessageElement);
        
        // 准备文件数据
        const fileData = await Promise.all(Array.from(files).map(file => {
            return new Promise((resolve, reject) => {
                const reader = new FileReader();
                reader.onload = e => resolve({
                    name: file.name,
                    type: file.type,
                    data: e.target.result
                });
                reader.onerror = reject;
                reader.readAsDataURL(file);
            });
        }));
        
        console.log('准备发送请求');
        
        // 发送请求
        const response = await fetch('/api/chat/stream', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                message: message,
                chat_id: currentChatId,
                files: fileData
            })
        });
        
        console.log('收到响应:', response.status);
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        // 处理流式响应
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let fullResponse = '';
        
        while (true) {
            const {value, done} = await reader.read();
            if (done) break;
            
            const chunk = decoder.decode(value);
            console.log('收到数据块:', chunk);
            
            const lines = chunk.split('\n');
            for (const line of lines) {
                if (line.startsWith('data: ')) {
                    try {
                        const data = JSON.parse(line.slice(6));
                        console.log('解析的数据:', data);
                        
                        if (data.error) {
                            throw new Error(data.error);
                        }
                        
                        if (data.content) {
                            fullResponse += data.content;
                            aiMessageContent.innerHTML = fullResponse.replace(/\n/g, '<br>');
                            chatBox.scrollTop = chatBox.scrollHeight;
                        }
                        
                        if (data.done) {
                            if (!currentChatId) {
                                currentChatId = data.chat_id;
                                updateHistoryList();
                            }
                            break;
                        }
                    } catch (parseError) {
                        console.error('解析SSE数据错误:', parseError);
                        throw parseError;
                    }
                }
            }
        }
        
    } catch (error) {
        console.error('发生错误:', error);
        const errorDiv = document.createElement('div');
        errorDiv.className = 'error-message';
        errorDiv.textContent = `错误: ${error.message}`;
        chatBox.appendChild(errorDiv);
        chatBox.scrollTop = chatBox.scrollHeight;
    } finally {
        // 清理和重置
        inputBox.value = '';
        inputBox.style.height = 'auto';
        fileInput.value = '';
        document.getElementById('file-preview').innerHTML = '';
        
        // 重新启用输入
        inputBox.disabled = false;
        setButtonState(false);
        isProcessing = false;
        inputBox.focus();
    }
}

// 更新历史记录列表
async function updateHistoryList() {
    try {
        const response = await fetch('/api/chat/history');
        const data = await response.json();
        
        const historyList = document.getElementById('history-list').querySelector('ul');
        if (!historyList) {
            console.error('找不到历史记录列表元素');
            return;
        }
        
        historyList.innerHTML = '';
        
        data.forEach(chat => {
            const listItem = document.createElement('li');
            listItem.setAttribute('role', 'listitem');
            const chatDiv = document.createElement('div');
            chatDiv.className = 'history-item';
            chatDiv.textContent = chat.title || '新对话';
            chatDiv.onclick = () => loadChat(chat.id);
            listItem.appendChild(chatDiv);
            historyList.appendChild(listItem);
        });
    } catch (error) {
        console.error('获取历史记录失败:', error);
    }
}

// 加载聊天记录
async function loadChat(chatId) {
    try {
        const response = await fetch(`/api/chat/${chatId}`);
        const data = await response.json();
        
        currentChatId = chatId;
        const chatBox = document.getElementById('chat-box');
        if (!chatBox) {
            console.error('找不到chat-box元素');
            return;
        }
        
        chatBox.innerHTML = '';
        
        data.messages.forEach(msg => {
            const messageElement = createMessageElement(msg.role, msg.content);
            chatBox.appendChild(messageElement);
        });
        
        chatBox.scrollTop = chatBox.scrollHeight;
    } catch (error) {
        console.error('加载对话失败:', error);
    }
}

// 开始新对话
function startNewChat() {
    console.log('开始新对话');
    currentChatId = null;
    const chatBox = document.getElementById('chat-box');
    if (chatBox) {
        chatBox.innerHTML = '';
    } else {
        console.error('找不到chat-box元素');
    }
}

// 处理文件上传
async function handleFileUpload(event) {
    const files = event.target.files;
    const filePreview = document.getElementById('file-preview');
    
    if (!filePreview) {
        console.error('找不到file-preview元素');
        return;
    }
    
    filePreview.innerHTML = '';
    currentFiles = [];
    
    for (const file of files) {
        if (!file.type.startsWith('image/') && file.type !== 'application/pdf') {
            alert('只支持图片和PDF文件');
            continue;
        }
        
        const previewContainer = document.createElement('div');
        previewContainer.className = 'preview-item';
        
        if (file.type.startsWith('image/')) {
            const reader = new FileReader();
            reader.onload = function(e) {
                const img = document.createElement('img');
                img.src = e.target.result;
                img.className = 'preview-image';
                previewContainer.appendChild(img);
                
                const deleteBtn = createDeleteButton(() => {
                    previewContainer.remove();
                    currentFiles = currentFiles.filter(f => f.name !== file.name);
                });
                previewContainer.appendChild(deleteBtn);
            };
            reader.readAsDataURL(file);
        } else if (file.type === 'application/pdf') {
            const pdfIcon = document.createElement('div');
            pdfIcon.className = 'pdf-icon';
            pdfIcon.innerHTML = `
                <svg viewBox="0 0 24 24" width="24" height="24">
                    <path fill="currentColor" d="M19 3H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2zm-9.5 8.5h2v1h-2v-1zm5 2H7v-1h7.5v1zm2-2H7v-1h9.5v1z"/>
                </svg>
                <span>${file.name}</span>
            `;
            previewContainer.appendChild(pdfIcon);
            
            const deleteBtn = createDeleteButton(() => {
                previewContainer.remove();
                currentFiles = currentFiles.filter(f => f.name !== file.name);
            });
            previewContainer.appendChild(deleteBtn);
        }
        
        filePreview.appendChild(previewContainer);
        
        try {
            const fileData = await fileToBase64(file);
            currentFiles.push({
                name: file.name,
                type: file.type,
                data: fileData
            });
        } catch (error) {
            console.error('文件处理错误:', error);
        }
    }
}

// 创建删除按钮
function createDeleteButton(onClick) {
    const deleteBtn = document.createElement('button');
    deleteBtn.className = 'delete-file-btn';
    deleteBtn.innerHTML = '×';
    deleteBtn.onclick = onClick;
    return deleteBtn;
}

// 文件转Base64
function fileToBase64(file) {
    return new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => resolve(reader.result);
        reader.onerror = reject;
        reader.readAsDataURL(file);
    });
}

// 处理表单提交
async function handleSubmit(event) {
    event.preventDefault();
    if (!isProcessing) {
        handleSendMessage();
    }
}