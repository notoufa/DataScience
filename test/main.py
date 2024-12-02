from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from typing import List, Optional
import base64
import dashscope
from http import HTTPStatus
import os
import json
import pytesseract
from PIL import Image
import fitz  # PyMuPDF
import io

app = FastAPI()

# 配置静态文件服务
app.mount("/assets", StaticFiles(directory="assets"), name="assets")

# 配置CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class FileData(BaseModel):
    data: str
    name: str
    type: str

class ChatMessage(BaseModel):
    message: str
    files: Optional[List[FileData]] = None

pytesseract.pytesseract.tesseract_cmd = r'E:\others\Tesseract-OCR'

def extract_text_from_image(image_data):
    """从图片中提取文本"""
    try:
        image = Image.open(io.BytesIO(image_data))
        text = pytesseract.image_to_string(image, lang='chi_sim+eng')
        return text.strip()
    except Exception as e:
        print(f"图片OCR错误: {str(e)}")
        return ""

def extract_text_from_pdf(pdf_data):
    """从PDF中提取文本"""
    try:
        pdf_document = fitz.open(stream=pdf_data, filetype="pdf")
        text = ""
        for page in pdf_document:
            text += page.get_text()
        return text.strip()
    except Exception as e:
        print(f"PDF解析错误: {str(e)}")
        return ""

@app.post("/api/chat")
async def chat(chat_message: ChatMessage):
    try:
        # 添加中文系统提示词
        messages = [{
            'role': 'system', 
            'content': '''你是一个专业的AI助手。
            1. 请始终使用中文回答问题
            2. 回答要简洁明了，重点突出
            3. 如果用户上传了图片或文档，请先分析其中的内容，然后再回答问题
            4. 如果不确定的内容，请明确告知用户
            5. 保持友好和专业的对话风格'''
        }]
        
        # 处理文件上传和内容提取
        file_contents = []
        if chat_message.files:
            print("接收到文件数量:", len(chat_message.files))  # 调试日志
            
            for file in chat_message.files:
                try:
                    print(f"处理文件: {file.name}, 类型: {file.type}")  # 调试日志
                    
                    # 确保数据是base64格式
                    if ',' in file.data:
                        file_data = base64.b64decode(file.data.split(',')[1])
                    else:
                        file_data = base64.b64decode(file.data)
                    
                    # 根据文件类型提取内容
                    if file.type.startswith('image/'):
                        content = extract_text_from_image(file_data)
                        print(f"图片OCR结果: {content[:100]}...")  # 调试日志
                        if content:
                            file_contents.append(f"图片'{file.name}'中的文本内容:\n{content}")
                        else:
                            file_contents.append(f"图片'{file.name}'中未能识别出文本内容。")
                    elif file.type == 'application/pdf':
                        content = extract_text_from_pdf(file_data)
                        print(f"PDF提取结果: {content[:100]}...")  # 调试日志
                        if content:
                            file_contents.append(f"PDF文件'{file.name}'中的文本内容:\n{content}")
                        else:
                            file_contents.append(f"PDF文件'{file.name}'中未能提取出文本内容。")
                except Exception as e:
                    print(f"处理文件 {file.name} 时出错: {str(e)}")
                    file_contents.append(f"处理文件'{file.name}'时发生错误: {str(e)}")
        
        # 构建用户消息
        user_message = chat_message.message
        if file_contents:
            file_content_text = "\n\n".join(file_contents)
            user_message = f"{user_message}\n\n===== 文件内容分析 =====\n{file_content_text}"
            print(f"发送给LLM的完整消息: {user_message[:200]}...")  # 调试日志
        
        messages.append({'role': 'user', 'content': user_message})
        
        # 调用模型
        print("调用LLM模型...")  # 调试日志
        response = dashscope.Generation.call(
            api_key='sk-0644acae22b64c389e55a6e3eea54f15',
            model='llama3.1-405b-instruct',
            messages=messages,
            result_format='message',
        )
        
        if response.status_code == HTTPStatus.OK:
            ai_response = response.output.choices[0].message.content
            print(f"LLM响应: {ai_response[:200]}...")  # 调试日志
            return {"response": ai_response}
        else:
            error_msg = f"API Error: {response.code} - {response.message}"
            print(f"LLM调用错误: {error_msg}")  # 调试日志
            raise HTTPException(status_code=500, detail=error_msg)
            
    except Exception as e:
        error_msg = f"Internal Server Error: {str(e)}"
        print(f"处理请求时出错: {error_msg}")  # 调试日志
        raise HTTPException(status_code=500, detail=error_msg)

@app.get("/")
async def read_root():
    with open("page/index.html", "r", encoding="utf-8") as f:
        html_content = f.read()
    return HTMLResponse(content=html_content, media_type="text/html")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 