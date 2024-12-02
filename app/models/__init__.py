from pydantic import BaseModel
from typing import List, Optional

class FileData(BaseModel):
    data: str
    name: str
    type: str

class ChatMessage(BaseModel):
    message: str
    files: Optional[List[FileData]] = None
