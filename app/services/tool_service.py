from langchain.tools import BaseTool
from langchain.agents import Tool
from vanna.remote import VannaDefault
import plotly
from typing import Optional, Type
from pydantic import BaseModel, Field

class DataQueryInput(BaseModel):
    query: str = Field(description="用户的数据查询请求")

class DataVisualizationInput(BaseModel):
    data: dict = Field(description="需要可视化的数据")
    
class DataAnalysisTool(BaseTool):
    name: str = "data_analysis"
    description: str = "用于执行数据库查询和分析的工具"
    args_schema: Type[BaseModel] = DataQueryInput
    vn: VannaDefault = None
    
    def __init__(self):
        super().__init__()
        self.vn = VannaDefault(model='test2820', api_key='6b837c6bf630461eab556b4223ed8c22')
        try:
            self.vn.connect_to_postgres(
                host='222.20.96.38',
                dbname='SiemensHarden_DB',
                user='postgres',
                password='Liu_123456',
                port='5432'
            )
        except Exception as e:
            print(f"数据库连接错误: {str(e)}")
    
    def _run(self, query: str) -> dict:
        try:
            # 生成SQL
            sql_query = self.vn.generate_sql(query)
            
            # 执行SQL获取数据
            data = self.vn.run_sql(sql_query)
            
            return {
                "sql": sql_query,
                "data": data,
                "status": "success"
            }
        except Exception as e:
            return {
                "error": str(e),
                "status": "error"
            }
    
    def _arun(self, query: str):
        raise NotImplementedError("暂不支持异步执行")

class DataVisualizationTool(BaseTool):
    name: str = "data_visualization"
    description: str = "用于生成数据可视化图表的工具"
    args_schema: Type[BaseModel] = DataVisualizationInput
    vn: VannaDefault = None
    
    def __init__(self):
        super().__init__()
        self.vn = VannaDefault(model='test2820', api_key='6b837c6bf630461eab556b4223ed8c22')
    
    def _run(self, data: dict) -> dict:
        try:
            # 生成可视化代码
            plotly_code = self.vn.generate_plotly_code(data)
            
            # 生成图表
            figure = self.vn.get_plotly_figure(plotly_code, data)
            if figure:
                plotly.offline.plot(figure, filename='temp_plot.html', auto_open=True)
            
            return {
                "message": "图表已生成并在新窗口打开",
                "status": "success"
            }
        except Exception as e:
            return {
                "error": str(e),
                "status": "error"
            }
    
    def _arun(self, data: dict):
        raise NotImplementedError("暂不支持异步执行")

class ToolService:
    def __init__(self):
        self.data_analysis_tool = DataAnalysisTool()
        self.data_visualization_tool = DataVisualizationTool()
        
        self.tools = [
            Tool(
                name="data_analysis",
                func=self.data_analysis_tool._run,
                description="""用于执行数据库查询和分析。
                输入：用户的查询请求（字符串）
                输出：包含SQL和查询结果的字典
                使用场景：
                - 当用户想查询数据库中的信息
                - 当用户需要统计或分析数据
                - 当用户提到"查询"、"数据"、"统计"等关键词
                示例输入："查询西门子相关的数据" """
            ),
            Tool(
                name="data_visualization",
                func=self.data_visualization_tool._run,
                description="""用于生成数据可视化图表。
                输入：需要可视化的数据（字典格式）
                输出：生成的图表信息
                使用场景：
                - 当用户需要将数据以图表形式展示
                - 当用户需要查看数据趋势
                - 当用户提到"图表"、"可视化"、"展示"等关键词
                示例输入：{"data": [...]} """
            )
        ] 