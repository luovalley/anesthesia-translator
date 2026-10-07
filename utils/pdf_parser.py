# utils/pdf_parser.py
import fitz  # PyMuPDF
import docx

def extract_structured_content(uploaded_file, start_page=1, end_page=None):
    """
    针对 Markdown 输出优化的解析器：
    精确解析 PDF、Word、MD、TXT，按阅读顺序提取纯文本。
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
            # 标记页面头部，方便在 Markdown 中划分层次
            elements.append({"type": "text", "content": f"\n\n## Page {page_num + 1}\n"})
            
            # 获取文本块并按垂直(y0)、水平(x0)坐标排序，完美兼顾医学文献的双栏排版
            blocks = page.get_text("blocks")
            sorted_blocks = sorted(blocks, key=lambda b: (b[1], b[0]))
            
            for b in sorted_blocks:
                block_type = b[6] if len(b) > 6 else 0
                if block_type == 0:  # 纯文本块
                    text = b[4].strip()
                    if text:
                        elements.append({"type": "text", "content": text})
                        
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
