import os
import logging
import asyncio
from typing import AsyncGenerator
from dotenv import load_dotenv
import json
import base64
from PIL import Image
import io
import fitz
import tempfile
import pytesseract
from langchain_openai import ChatOpenAI
from langchain.agents import initialize_agent, AgentType
from langchain.memory import ConversationBufferMemory
from langchain.callbacks.base import BaseCallbackHandler
from langchain.schema import HumanMessage, AIMessage, SystemMessage
from app.services.tool_service import ToolService
import threading
import queue
from app.core.config import settings
from app.services.tools import tools
from langchain_core.output_parsers.openai_tools import PydanticToolsParser

# 配置日志
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# 加载环境变量
load_dotenv()

class StreamingCallbackHandler(BaseCallbackHandler):
    def __init__(self):
        self.tokens = []
        self._queue = None
        self._error_queue = None
        self._loop = None

    def set_queues(self, queue: asyncio.Queue, error_queue: asyncio.Queue, loop: asyncio.AbstractEventLoop):
        self._queue = queue
        self._error_queue = error_queue
        self._loop = loop

    def on_llm_new_token(self, token: str, **kwargs) -> None:
        if self._queue and self._loop:
            try:
                future = asyncio.run_coroutine_threadsafe(
                    self._queue.put(token), 
                    self._loop
                )
                future.result()  # 等待操作完成
            except Exception as e:
                logger.error(f"放入token时出错: {str(e)}")
            
    def on_llm_error(self, error: Exception, **kwargs) -> None:
        logger.error(f"LLM错误: {str(error)}")
        if self._error_queue and self._loop:
            try:
                future = asyncio.run_coroutine_threadsafe(
                    self._error_queue.put(error), 
                    self._loop
                )
                future.result()  # 等待操作完成
            except Exception as e:
                logger.error(f"放入错误时出错: {str(e)}")
        
    def on_tool_error(self, error: Exception, **kwargs) -> None:
        logger.error(f"工具执行错误: {str(error)}")
        if self._error_queue and self._loop:
            try:
                future = asyncio.run_coroutine_threadsafe(
                    self._error_queue.put(error), 
                    self._loop
                )
                future.result()  # 等待操作完成
            except Exception as e:
                logger.error(f"放入工具错误时出错: {str(e)}")

class LLMService:
    def __init__(self):
        try:
            self.api_key = os.getenv('API_KEY')
            if not self.api_key:
                raise ValueError("API_KEY not found in environment variables")
            
            logger.info("初始化LLM服务...")
            
            # 初始化回调处理器
            self.callback_handler = StreamingCallbackHandler()
            
            # 初始化LangChain聊天模型
            self.llm = ChatOpenAI(
                base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
                model="llama3.1-405b-instruct",
                api_key=self.api_key
            )
            logger.info("LLM模型初始化成功")
            
            # 初始化工具服务
            self.tool_service = ToolService()
            logger.info("工具服务初始化成功")
            
            # 初始化代理
            self.memory = ConversationBufferMemory(
                memory_key="chat_history",
                return_messages=True,
                input_key="input",
                output_key="output"
            )
            
            # 设置代理的系统消息
            system_message = """你是一个专业的AI助手，可以帮助用户解答各种问题。你有以下工具可以使用：
            1. data_analysis工具：用于执行数据库查询和分析。当用户需要查询数据、统计数据或分析数据时使用。
            2. data_visualization工具：用于生成数据可视化图表。当用户需要图表展示、数据可视化或趋势分析时使用。
            
            当用户询问数据相关的问题时，你应该：
            1. 判断是否需要使用工具
            2. 选择合适的工具
            3. 使用工具执行操作
            4. 解释结果给用户
            
            请用中文回复。"""
            
            self.agent = initialize_agent(
                tools=self.tool_service.tools,
                llm=self.llm,
                agent=AgentType.CHAT_CONVERSATIONAL_REACT_DESCRIPTION,
                memory=self.memory,
                verbose=True,
                handle_parsing_errors=True,
                max_iterations=3,
                early_stopping_method="generate",
                agent_kwargs={
                    "system_message": system_message,
                    "input_key": "input",
                    "output_key": "output"
                }
            )
            logger.info("代理初始化成功")
            
            # 设置Tesseract路径
            tesseract_path = os.getenv('TESSERACT_CMD')
            if tesseract_path:
                pytesseract.pytesseract.tesseract_cmd = tesseract_path
            else:
                logger.warning("TESSERACT_CMD not found in environment variables")
                
            # 绑定工具到LLM
            self.llm_with_tools = self.llm.bind_tools(tools)
            # 创建输出解析器
            self.parser = PydanticToolsParser(tools=tools)
            
        except Exception as e:
            logger.error(f"初始化错误: {str(e)}")
            raise
    
    def process_image_ocr(self, image_data: str) -> str:
        """使用OCR处理图片并返回文本内容"""
        try:
            logger.info("开始处理图片OCR...")
            if 'base64,' in image_data:
                image_data = image_data.split('base64,')[1]
            
            # 解码base64数据
            image_bytes = base64.b64decode(image_data)
            image = Image.open(io.BytesIO(image_bytes))
            
            # 如果不是RGB模式，转换为RGB
            if image.mode != 'RGB':
                image = image.convert('RGB')
            
            # 使用OCR识别文本
            text = pytesseract.image_to_string(
                image, 
                lang='chi_sim+eng',
                config='--psm 3'
            )
            
            result = text.strip() if text.strip() else "图片中没有识别到文字内容。"
            logger.info(f"OCR处理完成: {result[:100]}...")
            return result
            
        except Exception as e:
            logger.error(f"OCR处理错误: {str(e)}")
            raise
    
    def process_pdf(self, pdf_data: str) -> str:
        """处理PDF文件并提取文本内容"""
        try:
            logger.info("开始处理PDF...")
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
            
            result = "\n".join(text_content)
            logger.info(f"PDF处理完成: {result[:100]}...")
            return result
            
        except Exception as e:
            logger.error(f"PDF处理错误: {str(e)}")
            raise
    
    async def get_response_stream(self, message: str, files=None) -> AsyncGenerator[str, None]:
        try:
            logger.info(f"收到用户消息: {message}")
            
            if not message:
                logger.error("收到空消息")
                yield "消息不能为空"
                return
            
            # 处理文件
            if files:
                file_contents = []
                for file in files:
                    try:
                        logger.info(f"处理文件: {file['type']}")
                        if file['type'].startswith('image/'):
                            image_text = self.process_image_ocr(file['data'])
                            if image_text:
                                file_contents.append(f"图片内容：\n{image_text}")
                        elif file['type'] == 'application/pdf':
                            pdf_text = self.process_pdf(file['data'])
                            file_contents.append(f"PDF内容：\n{pdf_text}")
                    except Exception as file_error:
                        logger.error(f"文件处理错误: {str(file_error)}")
                        yield f"\n处理文件时出现错误: {str(file_error)}"
                
                if file_contents:
                    message = f"{message}\n\n文件内容：\n" + "\n\n".join(file_contents)
            
            try:
                # 首先尝试检测是否需要数据分析
                needs_analysis = any(keyword in message.lower() for keyword in [
                    "分析", "统计", "查询", "数据", "图表", "趋势", "报表"
                ])
                
                if needs_analysis:
                    # 使用工具模式
                    logger.info("使用数据分析模式...")
                    
                    # 构建系统消息，包含工具使用说明
                    system_message = """你是一个专业的数据分析助手。你可以使用以下工具：
                    1. DataAnalysisTool: 用于执行西门子数据库的数据分析和生成可视化。
                    
                    当用户需要查询或分析数据时，你应该：
                    1. 理解用户的需求
                    2. 使用DataAnalysisTool工具执行查询
                    3. 解释结果给用户
                    
                    请用中文回复。"""
                    
                    messages = [
                        {"role": "system", "content": system_message},
                        {"role": "user", "content": message}
                    ]
                    
                    # 使用工具调用
                    response = await self.llm_with_tools.ainvoke(
                        messages,
                        config={
                            "tools": [
                                {
                                    "type": "function",
                                    "function": {
                                        "name": "DataAnalysisTool",
                                        "description": "执行西门子数据分析并生成可视化图表",
                                        "parameters": {
                                            "type": "object",
                                            "properties": {
                                                "query": {
                                                    "type": "string",
                                                    "description": "用户的查询问题"
                                                },
                                                "context": {
                                                    "type": "string",
                                                    "description": "查询的上下文信息"
                                                }
                                            },
                                            "required": ["query"]
                                        }
                                    }
                                }
                            ]
                        }
                    )
                    
                    logger.info(f"工具调用响应: {response}")
                    
                    # 解析工具调用
                    tool_calls = response.tool_calls if hasattr(response, 'tool_calls') else []
                    
                    if tool_calls:
                        # 使用解析器处理工具调用
                        parsed_tools = self.parser.parse(response)
                        
                        # 执行每个工具调用
                        for tool in parsed_tools:
                            result = tool.execute()
                            yield f"\n执行结果：{json.dumps(result, ensure_ascii=False)}"
                    
                    # 输出LLM的回复
                    content = response.content if hasattr(response, 'content') else str(response)
                    yield content
                    
                else:
                    # 使用普通对话模式
                    logger.info("使用普通对话模式...")
                    messages = [
                        {"role": "system", "content": "你是一个专业的AI助手，可以帮助用户解答各种问题。请用中文回复。"},
                        {"role": "user", "content": message}
                    ]
                    
                    response = await self.llm.ainvoke(
                        messages
                    )
                    
                    # 从响应中提取文本内容
                    if response:
                        content = response.content if hasattr(response, 'content') else str(response)
                        logger.info(f"生成的回复: {content}")
                        yield content
                    else:
                        logger.error("生成回复为空")
                        yield "抱歉，没有生成有效的回复"
                
            except Exception as process_error:
                logger.error(f"处理消息时出错: {str(process_error)}")
                yield f"\n处理消息时出现错误: {str(process_error)}"
                
        except Exception as e:
            logger.error(f"处理请求错误: {str(e)}")
            yield f"\n处理请求时出现错误: {str(e)}"
    
    async def process_message(self, message: str, chat_history: list = None) -> dict:
        try:
            logger.info(f"收到用户消息: {message}")
            
            # 更新对话历史
            if chat_history:
                for msg in chat_history:
                    self.memory.save_context(
                        {"input": msg["user"]},
                        {"output": msg["assistant"]}
                    )
            
            # 首先尝试检测是否需要数据分析
            needs_analysis = any(keyword in message.lower() for keyword in [
                "分析", "统计", "查询", "数据", "图表", "趋势", "报表"
            ])
            
            if needs_analysis:
                # 使用工具模式
                logger.info("使用数据分析模式...")
                response = await self.llm_with_tools.ainvoke(
                    message,
                    config={
                        "memory": self.memory,
                        "callbacks": None
                    }
                )
                
                # 解析工具调用
                tool_calls = response.tool_calls if hasattr(response, 'tool_calls') else []
                results = []
                
                if tool_calls:
                    # 使用解析器处理工具调用
                    parsed_tools = self.parser.parse(response)
                    
                    # 执行每个工具调用
                    for tool in parsed_tools:
                        result = tool.execute()
                        results.append(result)
                    
                    return {
                        "response": response.content if hasattr(response, 'content') else str(response),
                        "tool_results": results
                    }
            
            # 使用普通对话模式
            logger.info("使用普通对话模式...")
            response = await self.llm.agenerate(
                messages=[
                    SystemMessage(content="你是一个专业的AI助手，可以帮助用户解答各种问题。请用中文回复。"),
                    HumanMessage(content=message)
                ]
            )
            
            # 确保返回正确的响应格式
            if response and response.generations:
                # 从LLMResult中提取文本内容
                generation = response.generations[0][0]
                if hasattr(generation, 'message'):
                    content = generation.message.content
                else:
                    content = generation.text
                
                logger.info(f"生成的回复: {content}")
                
                # 保存到对话历史
                self.memory.save_context(
                    {"input": message},
                    {"output": content}
                )
                
                return {
                    "response": content,
                    "tool_results": []
                }
            else:
                logger.error("生成回复为空")
                return {
                    "error": "生成回复为空"
                }
            
        except Exception as e:
            logger.error(f"处理消息时出错: {str(e)}")
            return {
                "error": f"处理消息时出错: {str(e)}"
            } 