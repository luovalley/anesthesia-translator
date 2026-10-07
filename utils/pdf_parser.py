# utils/pdf_parser.py
import io
import fitz  # PyMuPDF
import docx

def extract_structured_content(uploaded_file, start_page=1, end_page=None):
    """
    解析 PDF 并返回结构化元素列表（包含通过显式 API 提取的图片）
    """
    file_name = uploaded_file.name
    file_extension = file_name.split(".")[-1].lower()
    
    elements = []
    
    if file_extension == "pdf":
        pdf_bytes = uploaded_file.read()
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        total_pages = len(doc)
        
        if end_page is None or end_page > total_pages:
            end_page = total_pages
            
        start_idx = max(0, start_page - 1)
        end_idx = min(total_pages, end_page)
        
        for page_num in range(start_idx, end_idx):
            page = doc[page_num]
            elements.append({"type": "text", "content": f"\n--- Page {page_num + 1} ---\n"})
            
            # 1. 提取并排序文本块
            blocks = page.get_text("blocks")
            sorted_blocks = sorted(blocks, key=lambda b: (b[1], b[0]))
            
            for b in sorted_blocks:
                block_type = b[6] if len(b) > 6 else 0
                if block_type == 0:
                    text = b[4].strip()
                    if text:
                        elements.append({"type": "text", "content": text})
            
            # 2. 显式提取该页面的所有图片对象
            image_list = page.get_images(full=True)
            for img_info in image_list:
                xref = img_info[0]
                try:
                    base_image = doc.extract_image(xref)
                    if base_image:
                        image_bytes = base_image["image"]
                        # 过滤掉过小的图标/装饰图（小于 3KB 的通常是小图标），保留正文插图
                        if len(image_bytes) > 3000:
                            elements.append({"type": "image", "data": image_bytes})
                except Exception:
                    pass
                        
        return elements, total_pages
        
    elif file_extension in ["docx", "doc"]:
        doc = docx.Document(uploaded_file)
        for p in doc.paragraphs:
            if p.text.strip():
                elements.append({"type": "text", "content": p.text})
        return elements, len(doc.paragraphs)
        
    elif file_extension in ["md", "txt"]:
        text_content = uploaded_file.read().decode("utf-8", errors="ignore")
        for line in text_content.split("\n"):
            if line.strip():
                elements.append({"type": "text", "content": line})
        return elements, len(text_content.split("\n"))
        
    return [], 0
