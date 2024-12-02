from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, StreamingResponse
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

app = FastAPI()

# 静态文件配置
app.mount("/assets", StaticFiles(directory="static/assets"), name="assets")
app.mount("/static", StaticFiles(directory="static"), name="static")

# 模板
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
    try:
        # 初始化Vanna
        vn = VannaDefault(model='test2820', api_key='6b837c6bf630461eab556b4223ed8c22')
        try:
            vn.connect_to_postgres(
                host='222.20.96.38',
                dbname='SiemensHarden_DB',
                user='postgres',
                password='Liu_123456',
                port='5432'
            )
        except Exception as db_error:
            print(f"Database connection error: {str(db_error)}")
            return {
                "error": f"数据库连接失败: {str(db_error)}"
            }
        
        try:
            # 生成SQL
            sql_query = vn.generate_sql(message.message)
            print(f"SQL Query: {sql_query}")
            
            try:
                # 执行SQL获取数据
                data = vn.run_sql(sql_query)
                print(f"Query Result: {data}")
                
                # 转换数据为可序列化的格式
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

                # 转换数据
                if isinstance(data, (pd.DataFrame, pd.Series)):
                    serializable_data = convert_to_serializable(data)
                else:
                    serializable_data = data
                
                try:
                    # 生成可视化代码
                    plotly_code = vn.generate_plotly_code(data)
                    print(f"Plotly Code: {plotly_code}")
                    
                    # 生成图表并显示
                    figure = vn.get_plotly_figure(plotly_code, data)
                    if figure:
                        import plotly
                        plotly.offline.plot(figure, filename='temp_plot.html', auto_open=True)
                        print("Figure displayed in browser")
                    
                    # 构建提示信息并获取分析
                    prompt = f"""请分析以下数据科学查询结果：

SQL查询：
{sql_query}

数据结果：
{serializable_data}

图表已在浏览器中打开，请提供专业的分析和见解。
"""
                    
                    try:
                        # 使用LLM生成分析结果
                        analysis = ""
                        async for chunk in llm_service.get_response_stream(prompt):
                            analysis += chunk
                        
                        # 返回结果（不包含图表数据）
                        return {
                            "sql": sql_query,
                            "data": serializable_data,
                            "analysis": analysis,
                            "message": "图表已在新窗口打开"
                        }
                    except Exception as llm_error:
                        print(f"LLM analysis error: {str(llm_error)}")
                        return {
                            "sql": sql_query,
                            "data": serializable_data,
                            "error": f"分析生成失败: {str(llm_error)}"
                        }
                        
                except Exception as viz_error:
                    print(f"Visualization error: {str(viz_error)}")
                    # 如果可视化失败，仍然返回SQL和数据
                    return {
                        "sql": sql_query,
                        "data": serializable_data,
                        "error": f"可视化生成失败: {str(viz_error)}"
                    }
                    
            except Exception as sql_error:
                print(f"SQL execution error: {str(sql_error)}")
                return {
                    "sql": sql_query,
                    "error": f"SQL执行失败: {str(sql_error)}"
                }
                
        except Exception as gen_error:
            print(f"SQL generation error: {str(gen_error)}")
            return {
                "error": f"SQL生成失败: {str(gen_error)}"
            }
            
    except Exception as e:
        print(f"Error in chat_dataScience: {str(e)}")
        return {
            "error": f"服务错误: {str(e)}"
        }

@app.post("/api/chat/stream")
async def chat_stream(message: ChatMessage):
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
            
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
    
    return StreamingResponse(event_generator(), media_type="text/event-stream")

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