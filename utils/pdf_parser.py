# utils/pdf_parser.py
import io
import fitz  # PyMuPDF
import docx

def extract_text_from_file(uploaded_file, start_page=1, end_page=None):
    """
    统一解析入口：支持 PDF、Word、MD、TXT
    返回: (plain_text_with_tags, image_list, total_units)
    """
    file_name = uploaded_file.name
    file_extension = file_name.split(".")[-1].lower()
    
    if file_extension == "pdf":
        pdf_bytes = uploaded_file.read()
        return parse_pdf_with_image_tags(pdf_bytes, start_page=start_page, end_page=end_page)
        
    elif file_extension in ["docx", "doc"]:
        doc = docx.Document(uploaded_file)
        plain_text = "\n".join([p.text for p in doc.paragraphs])
        return plain_text, [], len(doc.paragraphs)
        
    elif file_extension in ["md", "txt"]:
        plain_text = uploaded_file.read().decode("utf-8", errors="ignore")
        return plain_text, [], len(plain_text.split("\n"))
        
    else:
        return "不支持的文件格式。", [], 0

def parse_pdf_with_image_tags(pdf_bytes, start_page=1, end_page=None):
    """
    解析 PDF：双栏布局智能排序、提取内嵌图片并注入 [IMAGE_EMBED] 占位符
    """
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    total_pages = len(doc)
    
    if end_page is None or end_page > total_pages:
        end_page = total_pages
        
    start_idx = max(0, start_page - 1)
    end_idx = min(total_pages, end_page)
    
    content_pieces = []
    image_list = []
    
    for page_num in range(start_idx, end_idx):
        page = doc[page_num]
        blocks = page.get_text("blocks")
        
        # 按垂直坐标(y0)优先、水平坐标(x0)次之排序，兼顾双栏布局
        sorted_blocks = sorted(blocks, key=lambda b: (b[1], b[0]))
        
        page_pieces = [f"\n--- Page {page_num + 1} ---\n"]
        
        for b in sorted_blocks:
            block_type = b[6] if len(b) > 6 else 0
            if block_type == 0:  # 文本块
                text = b[4].strip()
                if text:
                    page_pieces.append(text)
            elif block_type == 1:  # 图片块
                try:
                    xref = b[7] if len(b) > 7 else None
                    base_image = doc.extract_image(xref) if xref else None
                    if base_image:
                        image_bytes = base_image["image"]
                        image_list.append(image_bytes)
                        # 插入图片占位符，以便翻译后精确定位插入
                        page_pieces.append("\n[IMAGE_EMBED]\n")
                except Exception:
                    pass
                    
        content_pieces.append("\n".join(page_pieces))
        
    combined_text = "\n\n".join(content_pieces)
    return combined_text, image_list, total_pages
