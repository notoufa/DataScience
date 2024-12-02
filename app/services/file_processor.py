import base64
import pytesseract
from PIL import Image
import fitz
import io

class FileProcessor:
    def __init__(self):
        pytesseract.pytesseract.tesseract_cmd = r'E:\others\Tesseract-OCR'

    def extract_text_from_image(self, image_data):
        """从图片中提取文本"""
        try:
            image = Image.open(io.BytesIO(image_data))
            text = pytesseract.image_to_string(image, lang='chi_sim+eng')
            return text.strip()
        except Exception as e:
            print(f"图片OCR错误: {str(e)}")
            return ""

    def extract_text_from_pdf(self, pdf_data):
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

    def process_file(self, file):
        """处理单个文件"""
        try:
            if ',' in file.data:
                file_data = base64.b64decode(file.data.split(',')[1])
            else:
                file_data = base64.b64decode(file.data)

            if file.type.startswith('image/'):
                content = self.extract_text_from_image(file_data)
                return f"图片'{file.name}'中的文本内容:\n{content}" if content else f"图片'{file.name}'中未能识别出文本内容。"
            
            elif file.type == 'application/pdf':
                content = self.extract_text_from_pdf(file_data)
                return f"PDF文件'{file.name}'中的文本内容:\n{content}" if content else f"PDF文件'{file.name}'中未能提取出文本内容。"
            
        except Exception as e:
            return f"处理文件'{file.name}'时发生错误: {str(e)}" 