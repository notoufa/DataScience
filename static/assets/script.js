const chatBox = document.getElementById('chat-box');
const inputBox = document.getElementById('input-box');
const sendButton = document.getElementById('send-button');

let currentFiles = [];
let chatHistory = [];
let currentChatId = null;
let isProcessing = false;

async function sendMessage() {
    if (isProcessing) {
        return;
    }

    const message = inputBox.value.trim();
    if (!message && currentFiles.length === 0) return;
    
    try {
        isProcessing = true;
        
        inputBox.disabled = true;
        const sendButton = document.getElementById('send-button');
        sendButton.disabled = true;
        sendButton.style.opacity = '0.5';
        
        inputBox.value = '';
        const filePreview = document.getElementById('file-preview');
        filePreview.innerHTML = '';
        
        appendMessage('user', message, currentFiles);
        
        const isDataScienceMode = document.getElementById('data-science-mode').checked;
        const endpoint = isDataScienceMode ? '/api/chat/dataScience' : '/api/chat/stream';
        
        const aiMessageDiv = createMessageElement('', false);
        chatBox.appendChild(aiMessageDiv);
        const aiMessageContent = aiMessageDiv.querySelector('.message-content');
        
        const response = await fetch(endpoint, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                message: message,
                chat_id: currentChatId,
                files: currentFiles
            })
        });
        
        if (isDataScienceMode) {
            const data = await response.json();
            if (data.error) {
                throw new Error(data.error);
            }
            
            let resultContent = '<div class="datascience-response">';
            
            if (data.sql) {
                resultContent += `
                    <div class="code-block">
                        <div class="code-header">SQL查询</div>
                        <pre><code class="sql">${data.sql}</code></pre>
                    </div>`;
            }
            
            if (data.data) {
                let formattedData;
                try {
                    formattedData = typeof data.data === 'string' ? 
                        data.data : JSON.stringify(data.data, null, 2);
                } catch (e) {
                    formattedData = data.data.toString();
                }
                
                resultContent += `
                    <div class="data-block">
                        <div class="data-header">查询结果</div>
                        <pre class="data-content">${formattedData}</pre>
                    </div>`;
            }
            
            if (data.message) {
                resultContent += `
                    <div class="message-block">
                        <div class="message-header">提示</div>
                        <div class="message-content">${data.message}</div>
                    </div>`;
            }
            
            if (data.analysis) {
                resultContent += `
                    <div class="analysis-block">
                        <div class="analysis-header">分析结果</div>
                        <div class="analysis-content">${data.analysis.replace(/\n/g, '<br>')}</div>
                    </div>`;
            }
            
            resultContent += '</div>';
            aiMessageContent.innerHTML = resultContent;
            
            chatBox.scrollTop = chatBox.scrollHeight;
        } else {
            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let fullResponse = '';
            
            while (true) {
                const {value, done} = await reader.read();
                if (done) break;
                
                const chunk = decoder.decode(value);
                const lines = chunk.split('\n');
                
                for (const line of lines) {
                    if (line.startsWith('data: ')) {
                        const data = JSON.parse(line.slice(6));
                        
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
                    }
                }
            }
        }
        
    } catch (error) {
        appendMessage('error', '抱歉，发生了错误，请稍后重试');
        console.error('Error:', error);
    } finally {
        inputBox.disabled = false;
        const sendButton = document.getElementById('send-button');
        sendButton.disabled = false;
        sendButton.style.opacity = '1';
        isProcessing = false;
        currentFiles = [];
        inputBox.focus();
    }
}

function appendMessage(role, content, files = []) {
    const messageDiv = createMessageElement(content, role === 'user', files);
    chatBox.appendChild(messageDiv);
    chatBox.scrollTop = chatBox.scrollHeight;
}

function createMessageElement(content, isUser, files = []) {
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${isUser ? 'user-message' : 'assistant-message'}`;
    
    const avatarContainer = document.createElement('div');
    avatarContainer.className = 'avatar-container';
    
    const avatar = document.createElement('img');
    avatar.className = 'avatar';
    
    if (isUser) {
        avatar.src = '/static/picture/user.jpg';
    } else {
        avatar.src = '/static/picture/LLM.png';
    }
    
    avatar.alt = isUser ? '用户' : 'AI';
    
    avatar.onerror = function() {
        console.error('Failed to load image:', this.src);
        this.style.backgroundColor = isUser ? '#10a37f' : '#098aa0';
        this.style.color = 'white';
        this.style.display = 'flex';
        this.style.alignItems = 'center';
        this.style.justifyContent = 'center';
        this.textContent = isUser ? 'U' : 'AI';
    };
    
    avatarContainer.appendChild(avatar);
    
    const messageContent = document.createElement('div');
    messageContent.className = 'message-content';
    messageContent.innerHTML = content.replace(/\n/g, '<br>');
    
    const timestamp = new Date().toLocaleTimeString();
    messageDiv.setAttribute('data-time', timestamp);
    
    if (files && files.length > 0) {
        const filesContainer = document.createElement('div');
        filesContainer.className = 'message-files';
        
        files.forEach(file => {
            const filePreview = document.createElement('div');
            filePreview.className = 'message-file-item';
            
            if (file.type.startsWith('image/')) {
                const img = document.createElement('img');
                img.src = file.data;
                img.alt = file.name;
                img.onclick = () => window.open(file.data, '_blank');
                filePreview.appendChild(img);
            } else if (file.type === 'application/pdf') {
                const pdfIcon = document.createElement('div');
                pdfIcon.className = 'pdf-preview';
                pdfIcon.innerHTML = `
                    <svg viewBox="0 0 24 24" width="48" height="48">
                        <path fill="currentColor" d="M19 3H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2zm-9.5 8.5h2v1h-2v-1zm5 2H7v-1h7.5v1zm2-2H7v-1h9.5v1z"/>
                    </svg>
                    <span>${file.name}</span>
                `;
                pdfIcon.onclick = () => window.open(file.data, '_blank');
                filePreview.appendChild(pdfIcon);
            }
            
            filesContainer.appendChild(filePreview);
        });
        
        messageContent.appendChild(filesContainer);
    }
    
    if (isUser) {
        messageDiv.appendChild(messageContent);
        messageDiv.appendChild(avatarContainer);
    } else {
        messageDiv.appendChild(avatarContainer);
        messageDiv.appendChild(messageContent);
    }
    
    return messageDiv;
}

function showLoadingMessage() {
    const chatBox = document.getElementById('chat-box');
    const loadingDiv = document.createElement('div');
    loadingDiv.className = 'message assistant-message loading';
    loadingDiv.id = 'loading-message';
    loadingDiv.innerHTML = `
        <div class="message-icon">
            <svg>...</svg>
        </div>
        <div class="message-content">
            <div class="loading-dots">
                <span></span>
                <span></span>
                <span></span>
            </div>
        </div>
    `;
    chatBox.appendChild(loadingDiv);
    chatBox.scrollTop = chatBox.scrollHeight;
}

function removeLoadingMessage() {
    const loadingMessage = document.getElementById('loading-message');
    if (loadingMessage) {
        loadingMessage.remove();
    }
}

function handleKeyDown(event) {
    if (event.key === 'Enter' && !event.shiftKey && !isProcessing) {
        event.preventDefault();
        sendMessage();
    }
}

function startNewChat() {
    currentChatId = null;
    const chatBox = document.getElementById('chat-box');
    chatBox.innerHTML = '';
}

async function updateHistoryList() {
    try {
        const response = await fetch('/api/chat/history');
        const data = await response.json();
        
        const historyList = document.getElementById('history-list');
        historyList.innerHTML = '';
        
        data.forEach(chat => {
            const chatDiv = document.createElement('div');
            chatDiv.className = 'history-item';
            chatDiv.textContent = chat.title || '新对话';
            chatDiv.onclick = () => loadChat(chat.id);
            historyList.appendChild(chatDiv);
        });
    } catch (error) {
        console.error('获取历史记录失败:', error);
    }
}

async function loadChat(chatId) {
    try {
        const response = await fetch(`/api/chat/${chatId}`);
        const data = await response.json();
        
        currentChatId = chatId;
        const chatBox = document.getElementById('chat-box');
        chatBox.innerHTML = '';
        
        data.messages.forEach(msg => {
            appendMessage(msg.role, msg.content);
        });
    } catch (error) {
        console.error('加载对话失败:', error);
    }
}

document.addEventListener('DOMContentLoaded', () => {
    updateHistoryList();
});

async function handleFileUpload(event) {
    const files = event.target.files;
    const filePreview = document.getElementById('file-preview');
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
        
        const fileData = {
            name: file.name,
            type: file.type,
            data: await fileToBase64(file)
        };
        currentFiles.push(fileData);
    }
}

function createDeleteButton(onClick) {
    const deleteBtn = document.createElement('button');
    deleteBtn.className = 'delete-file-btn';
    deleteBtn.innerHTML = '×';
    deleteBtn.onclick = onClick;
    return deleteBtn;
}

function fileToBase64(file) {
    return new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => resolve(reader.result);
        reader.onerror = reject;
        reader.readAsDataURL(file);
    });
}