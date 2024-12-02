import os
from typing import AsyncGenerator
from dotenv import load_dotenv
from openai import OpenAI
import json
import asyncio
import base64
from PIL import Image
import io
import fitz
import tempfile
import pytesseract

# 加载环境变量
load_dotenv()

class LLMService:
    def __init__(self):
        self.api_key = os.getenv('API_KEY')
        if not self.api_key:
            raise ValueError("API_KEY not found in environment variables")
        
        self.client = OpenAI(
            api_key=self.api_key,
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1"
        )
        
        self.model = 'llama3.1-405b-instruct'
        
        # 设置Tesseract路径
        tesseract_path = os.getenv('TESSERACT_CMD')
        if tesseract_path:
            pytesseract.pytesseract.tesseract_cmd = os.path.join(tesseract_path, 'tesseract.exe')
        else:
            raise ValueError("TESSERACT_CMD not found in environment variables")
    
    def process_image_ocr(self, image_data: str) -> str:
        """使用OCR处理图片并返回文本内容"""
        try:
            if 'base64,' in image_data:
                image_data = image_data.split('base64,')[1]
            
            # 解码base64数据
            image_bytes = base64.b64decode(image_data)
            image = Image.open(io.BytesIO(image_bytes))
            
            # 如果不是RGB模式，转换为RGB
            if image.mode != 'RGB':
                image = image.convert('RGB')
            
            # 使用OCR识别文本，添加配置参数
            text = pytesseract.image_to_string(
                image, 
                lang='chi_sim+eng',  # 支持中文和英文
                config='--psm 3'     # 自动检测页面分割和方向
            )
            
            # 如果没有识别到文本，返回提示信息
            if not text.strip():
                return "图片中没有识别到文字内容。"
                
            return text.strip()
            
        except Exception as e:
            raise Exception(f"OCR处理错误: {str(e)}")
    
    def process_pdf(self, pdf_data: str) -> str:
        """处理PDF文件并提取文本内容"""
        try:
            if 'base64,' in pdf_data:
                pdf_data = pdf_data.split('base64,')[1]
            
            pdf_bytes = base64.b64decode(pdf_data)
            
            with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as temp_pdf:
                temp_pdf.write(pdf_bytes)
                temp_pdf_path = temp_pdf.name
            
            text_content = []
            try:
                doc = fitz.open(temp_pdf_path)
                for page in doc:
                    text_content.append(page.get_text())
                doc.close()
            finally:
                os.unlink(temp_pdf_path)
            
            return "\n".join(text_content)
            
        except Exception as e:
            raise Exception(f"PDF处理错误: {str(e)}")
    
    async def get_response_stream(self, message: str, files=None) -> AsyncGenerator[str, None]:
        try:
            messages = [
                {'role': 'system', 'content': '你是一个专业的AI助手，可以帮助用户解答各种问题。'}
            ]
            
            # 处理文件
            if files:
                for file in files:
                    if file['type'].startswith('image/'):
                        image_text = self.process_image_ocr(file['data'])
                        if image_text:
                            messages.append({
                                'role': 'user',
                                'content': f"这是图片中的文字内容：\n\n{image_text}"
                            })
                    elif file['type'] == 'application/pdf':
                        pdf_text = self.process_pdf(file['data'])
                        messages.append({
                            'role': 'user',
                            'content': f"这是PDF文档的内容：\n\n{pdf_text}"
                        })
            
            # 添加用户文本消息
            if message:
                messages.append({
                    'role': 'user',
                    'content': message
                })
            elif not message and files:
                messages.append({
                    'role': 'user',
                    'content': "请分析上述文件内容"
                })
            
            # 使用LLM处理文本
            completion = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                stream=True,
                stream_options={"include_usage": True}
            )
            
            for chunk in completion:
                chunk_data = json.loads(chunk.model_dump_json())
                if 'choices' in chunk_data and chunk_data['choices']:
                    content = chunk_data['choices'][0].get('delta', {}).get('content')
                    if content:
                        yield content
                        await asyncio.sleep(0.005)
                
        except Exception as e:
            raise Exception(f"LLM服务错误: {str(e)}") 