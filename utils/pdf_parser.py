# utils/pdf_parser.py
import io
import fitz  # PyMuPDF
import docx

def extract_structured_content(uploaded_file, start_page=1, end_page=None):
    """
    升级版解析器：不仅提取文本，还将每一页整体渲染为高清排版图片，
    确保文献中的所有图表、曲线、双栏排版 100% 完美保留。
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
            
            # 1. 提取文本块
            blocks = page.get_text("blocks")
            sorted_blocks = sorted(blocks, key=lambda b: (b[1], b[0]))
            
            for b in sorted_blocks:
                block_type = b[6] if len(b) > 6 else 0
                if block_type == 0:
                    text = b[4].strip()
                    if text:
                        elements.append({"type": "text", "content": text})
            
            # 2. 将整页渲染为高清晰度图片（DIP 缩放 2.0，保证图表与公式清晰）
            try:
                pix = page.get_pixmap(dpi=150)
                page_img_bytes = pix.tobytes("png")
                elements.append({"type": "image", "data": page_img_bytes})
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
