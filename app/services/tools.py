from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
import pandas as pd
from vanna.remote import VannaDefault
from app.core.config import settings

class DataAnalysisTool(BaseModel):
    """执行西门子数据分析并生成可视化图表。"""
    
    query: str = Field(..., description="用户的查询问题")
    context: Optional[str] = Field(None, description="查询的上下文信息")

    def execute(self) -> Dict[str, Any]:
        """执行数据分析并生成可视化"""
        try:
            # 初始化Vanna
            vn = VannaDefault(model=settings.VANNA_MODEL, api_key=settings.VANNA_API_KEY)
            
            # 数据库连接
            vn.connect_to_postgres(
                host=settings.DB_HOST,
                dbname=settings.DB_NAME,
                user=settings.DB_USER,
                password=settings.DB_PASSWORD,
                port=settings.DB_PORT
            )
            
            # 生成SQL
            sql_query = vn.generate_sql(self.query)
            if not sql_query:
                return {
                    "status": "error",
                    "message": "无法生成SQL查询"
                }
            
            # 执行SQL获取数据
            data = vn.run_sql(sql_query)
            if data is None or (isinstance(data, pd.DataFrame) and data.empty):
                return {
                    "status": "success",
                    "sql": sql_query,
                    "message": "查询结果为空"
                }
            
            # 数据序列化
            df = data if isinstance(data, pd.DataFrame) else pd.DataFrame(data)
            serializable_data = df.to_dict(orient='records')
            
            # 生成可视化
            try:
                plotly_code = vn.generate_plotly_code(df)
                figure = vn.get_plotly_figure(plotly_code, df)
                
                if figure:
                    import plotly
                    plot_path = 'static/temp_plot.html'
                    plotly.offline.plot(figure, filename=plot_path, auto_open=False)
                    
                    return {
                        "status": "success",
                        "sql": sql_query,
                        "data": serializable_data,
                        "plot_url": "/static/temp_plot.html",
                        "message": "分析和可视化生成成功"
                    }
            except Exception as viz_error:
                # 如果可视化失败，仍然返回数据分析结果
                return {
                    "status": "partial_success",
                    "sql": sql_query,
                    "data": serializable_data,
                    "message": f"数据分析成功，但可视化生成失败: {str(viz_error)}"
                }
            
        except Exception as e:
            return {
                "status": "error",
                "message": f"数据分析错误: {str(e)}"
            }

# 导出工具列表
tools = [DataAnalysisTool] 