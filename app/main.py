from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from typing import Optional
import uuid
import json
from app.services.llm_service import LLMService
from vanna.remote import VannaDefault
import base64
import io
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from app.core.config import settings
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Cache-Control"] = "public, max-age=31536000"
        return response

app = FastAPI()

# 添加中间件
app.add_middleware(SecurityHeadersMiddleware)

# 添加CORS中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 静态文件配置
app.mount("/static", StaticFiles(directory="static", html=True, check_dir=True), name="static")
app.mount("/assets", StaticFiles(directory="static/assets", html=True, check_dir=True), name="assets")

# 添加图片文件类型支持
@app.get("/static/picture/{filename}")
async def get_image(filename: str):
    return FileResponse(
        f"static/picture/{filename}",
        headers={
            "Cache-Control": "public, max-age=31536000",
            "X-Content-Type-Options": "nosniff"
        }
    )

# 模板配置
templates = Jinja2Templates(directory="templates")

# LLM服务实例
llm_service = LLMService()

# 存储聊天历史
chat_history = {}

class ChatMessage(BaseModel):
    message: str
    chat_id: Optional[str] = None
    files: Optional[list] = None

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/api/chat/dataScience")
async def chat_dataScience(message: ChatMessage):
    if not message.message:
        raise HTTPException(status_code=400, detail="消息内容不能为空")
        
    try:
        # 初始化Vanna
        vn = VannaDefault(model=settings.VANNA_MODEL, api_key=settings.VANNA_API_KEY)
        
        # 数据库连接
        try:
            vn.connect_to_postgres(
                host=settings.DB_HOST,
                dbname=settings.DB_NAME,
                user=settings.DB_USER,
                password=settings.DB_PASSWORD,
                port=settings.DB_PORT
            )
        except Exception as db_error:
            print(f"Database connection error: {str(db_error)}")
            return {"status": "error", "message": f"数据库连接失败: {str(db_error)}"}

        try:
            # 生成SQL
            sql_query = vn.generate_sql(message.message)
            if not sql_query:
                return {"status": "error", "message": "无法生成SQL查询"}

            print(f"Generated SQL: {sql_query}")
            
            # 执行SQL获取数据
            try:
                data = vn.run_sql(sql_query)
                if data is None or (isinstance(data, pd.DataFrame) and data.empty):
                    return {
                        "status": "success",
                        "sql": sql_query,
                        "message": "查询结果为空"
                    }
                
                # 数据序列化
                serializable_data = convert_to_serializable(data)
                
                # 尝试生成可视化
                try:
                    plotly_code = vn.generate_plotly_code(data)
                    figure = vn.get_plotly_figure(plotly_code, data)
                    
                    if figure:
                        import plotly
                        plot_path = 'static/temp_plot.html'
                        plotly.offline.plot(figure, filename=plot_path, auto_open=False)
                        
                        return {
                            "status": "success",
                            "sql": sql_query,
                            "data": serializable_data,
                            "plot_url": "/static/temp_plot.html",
                            "message": "查询成功"
                        }
                    
                except Exception as viz_error:
                    print(f"Visualization error: {str(viz_error)}")
                    return {
                        "status": "success",
                        "sql": sql_query,
                        "data": serializable_data,
                        "message": "数据查询成功，但可视化生成失败"
                    }
                    
            except Exception as sql_error:
                print(f"SQL execution error: {str(sql_error)}")
                return {"status": "error", "message": f"SQL执行失败: {str(sql_error)}"}
                
        except Exception as gen_error:
            print(f"SQL generation error: {str(gen_error)}")
            return {"status": "error", "message": f"SQL生成失败: {str(gen_error)}"}
            
    except Exception as e:
        print(f"General error: {str(e)}")
        return {"status": "error", "message": f"服务错误: {str(e)}"}

def convert_to_serializable(obj):
    if isinstance(obj, (np.integer, np.floating)):
        return float(obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    elif isinstance(obj, pd.DataFrame):
        return obj.to_dict(orient='records')
    elif isinstance(obj, pd.Series):
        return obj.to_dict()
    return obj

@app.post("/api/chat/stream")
async def chat_stream(message: ChatMessage):
    if not message.message:
        return StreamingResponse(
            iter([f"data: {json.dumps({'error': '消息内容不能为空'})}\n\n"]),
            media_type="text/event-stream"
        )

    async def event_generator():
        try:
            # 创建或获取chat_id
            chat_id = message.chat_id or str(uuid.uuid4())
            if chat_id not in chat_history:
                chat_history[chat_id] = []
            
            # 保存用户消息和文件
            chat_history[chat_id].append({
                "role": "user",
                "content": message.message,
                "files": message.files
            })
            
            # 初始化AI响应
            full_response = ""
            
            try:
                # 获取流式响应
                async for chunk in llm_service.get_response_stream(message.message, message.files):
                    full_response += chunk
                    # 发送SSE格式的数据
                    yield f"data: {json.dumps({'content': chunk, 'done': False})}\n\n"
                
                # 保存完整响应到历史记录
                chat_history[chat_id].append({
                    "role": "assistant",
                    "content": full_response
                })
                
                # 发送完成信号
                yield f"data: {json.dumps({'content': '', 'done': True, 'chat_id': chat_id})}\n\n"
            
            except Exception as stream_error:
                print(f"Streaming error: {str(stream_error)}")
                yield f"data: {json.dumps({'error': f'流式响应错误: {str(stream_error)}'})}\n\n"
                
        except Exception as e:
            print(f"General error in chat stream: {str(e)}")
            yield f"data: {json.dumps({'error': f'服务错误: {str(e)}'})}\n\n"
    
    return StreamingResponse(
        event_generator(), 
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Content-Type-Options": "nosniff"
        }
    )

@app.get("/api/chat/history")
async def get_chat_history():
    try:
        history_list = []
        for chat_id, messages in chat_history.items():
            # 获取第一条用户消息作为标题
            title = next((msg["content"][:30] + "..." for msg in messages if msg["role"] == "user"), "新对话")
            history_list.append({
                "id": chat_id,
                "title": title
            })
        return history_list
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/chat/{chat_id}")
async def get_chat(chat_id: str):
    try:
        if chat_id not in chat_history:
            raise HTTPException(status_code=404, detail="Chat not found")
        return {"messages": chat_history[chat_id]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)