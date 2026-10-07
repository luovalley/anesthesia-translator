import io
import fitz  # PyMuPDF
import docx
from docx.shared import Inches, Pt

def extract_text_from_file(uploaded_file, start_page=1, end_page=None):
    """
    统一解析入口：支持 PDF、Word、MD、TXT
    返回: (doc_io, plain_text, total_units)
    """
    file_name = uploaded_file.name
    file_extension = file_name.split(".")[-1].lower()
    
    if file_extension == "pdf":
        pdf_bytes = uploaded_file.read()
        return parse_pdf_to_docx_and_text(pdf_bytes, start_page=start_page, end_page=end_page)
        
    elif file_extension in ["docx", "doc"]:
        doc = docx.Document(uploaded_file)
        plain_text = "\n".join([p.text for p in doc.paragraphs])
        doc_io = io.BytesIO()
        doc.save(doc_io)
        doc_io.seek(0)
        return doc_io, plain_text, len(doc.paragraphs)
        
    elif file_extension in ["md", "txt"]:
        plain_text = uploaded_file.read().decode("utf-8", errors="ignore")
        doc = docx.Document()
        for line in plain_text.split("\n"):
            doc.add_paragraph(line)
        doc_io = io.BytesIO()
        doc.save(doc_io)
        doc_io.seek(0)
        return doc_io, plain_text, len(plain_text.split("\n"))
        
    else:
        doc = docx.Document()
        doc.add_paragraph("不支持的文件格式。")
        doc_io = io.BytesIO()
        doc.save(doc_io)
        doc_io.seek(0)
        return doc_io, "不支持的文件格式。", 0

def parse_pdf_to_docx_and_text(pdf_bytes, start_page=1, end_page=None):
    """
    解析 PDF：双栏布局智能排序、提取内嵌图片、生成 Word 字节流与纯文本
    """
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    total_pages = len(doc)
    
    if end_page is None or end_page > total_pages:
        end_page = total_pages
        
    # 调整为 0-based 索引
    start_idx = max(0, start_page - 1)
    end_idx = min(total_pages, end_page)
    
    word_doc = docx.Document()
    all_extracted_texts = []
    
    for page_num in range(start_idx, end_idx):
        page = doc[page_num]
        
        # 1. 获取页面中的所有文本块 (格式: [x0, y0, x1, y1, text, block_no, block_type])
        blocks = page.get_text("blocks")
        
        # 2. 获取页面中的图片信息
        image_list = page.get_images(full=True)
        
        # 简单按垂直坐标(y0)排序，兼顾双栏或多栏的纵向阅读顺序
        # 如果需要更精准的双栏分栏，可按 x 坐标切分，这里采用通用的按垂直位置优先排序
        sorted_blocks = sorted(blocks, key=lambda b: (b[1], b[0]))
        
        page_text_pieces = []
        for b in sorted_blocks:
            block_type = b[6] if len(b) > 6 else 0
            if block_type == 0:  # 文本块
                text = b[4].strip()
                if text:
                    page_text_pieces.append(text)
                    word_doc.add_paragraph(text)
            elif block_type == 1:  # 图片块
                # 尝试从 PDF 中提取并内嵌图片
                try:
                    xref = b[7] if len(b) > 7 else None
                    # 如果有直接关联的图片 xref，或者遍历提取
                    base_image = doc.extract_image(xref) if xref else None
                    if base_image:
                        image_bytes = base_image["image"]
                        image_stream = io.BytesIO(image_bytes)
                        word_doc.add_picture(image_stream, width=Inches(4.0))
                        page_text_pieces.append("[图片已内嵌]")
                except Exception:
                    pass
                    
        # 页面分隔提示
        page_full_text = "\n".join(page_text_pieces)
        all_extracted_texts.append(f"--- Page {page_num + 1} ---\n" + page_full_text)
        
        if page_num < end_idx - 1:
            word_doc.add_page_break()
            
    # 保存为内存中的 Word 二进制流
    doc_io = io.BytesIO()
    word_doc.save(doc_io)
    doc_io.seek(0)
    
    combined_plain_text = "\n\n".join(all_extracted_texts)
    
    return doc_io, combined_plain_text, total_pages
