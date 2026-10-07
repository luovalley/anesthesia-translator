import os
import io
import fitz  # PyMuPDF
import docx
from docx.shared import Inches

def extract_text_from_file(uploaded_file, start_page=1, end_page=None):
    """
    统一入口：同时返回 Word 内存流、用于大模型翻译的纯文本、以及单元数
    """
    file_name = uploaded_file.name
    file_extension = file_name.split(".")[-1].lower()
    
    if file_extension == "pdf":
        pdf_bytes = uploaded_file.read()
        doc_io, plain_text = parse_pdf_to_docx_and_text(pdf_bytes, start_page=start_page, end_page=end_page)
        return doc_io, plain_text, len(plain_text)
    elif file_extension in ["docx", "doc"]:
        doc = docx.Document(uploaded_file)
        plain_text = "\n".join([p.text for p in doc.paragraphs])
        doc_io = io.BytesIO()
        doc.save(doc_io)
        doc_io.seek(0)
        return doc_io, plain_text, len(plain_text)
    elif file_extension in ["md", "txt"]:
        plain_text = uploaded_file.read().decode("utf-8", errors="ignore")
        doc = docx.Document()
        for line in plain_text.split("\n"):
            doc.add_paragraph(line)
        doc_io = io.BytesIO()
        doc.save(doc_io)
        doc_io.seek(0)
        return doc_io, plain_text, len(plain_text)
    else:
        doc = docx.Document()
        doc.add_paragraph("不支持的文件格式。")
        doc_io = io.BytesIO()
        doc.save(doc_io)
        doc_io.seek(0)
        return doc_io, "不支持的文件格式。", 0

def parse_pdf_to_docx(pdf_bytes, start_page=1, end_page=None):
    """
    针对双栏医学文献优化的 PDF 解析器：直接生成排版规整、图片内嵌的 Word 文档
    """
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    output_doc = docx.Document()

    total_pages = len(doc)
    start_idx = max(0, start_page - 1)
    end_idx = min(total_pages, end_page) if end_page else total_pages

    for page_num in range(start_idx, end_idx):
        page = doc[page_num]
        output_doc.add_heading(f"--- Page {page_num + 1} ---", level=3)
        
        page_width = page.rect.width
        mid_x = page_width / 2.0

        # 获取文本块
        blocks = page.get_text("blocks", sort=True)
        
        # 提取页面内嵌图片及其坐标
        image_list = page.get_images(full=True)
        image_elements = []
        for img_index, img_info in enumerate(image_list):
            xref = img_info[0]
            rects = page.get_image_rects(xref)
            for r in rects:
                pix = fitz.Pixmap(doc, xref)
                if pix.n >= 5:
                    pix = fitz.Pixmap(fitz.csRGB, pix)
                img_bytes = pix.tobytes("png")
                pix = None
                
                col = 0 if r.x0 < mid_x else 1
                image_elements.append({
                    "y0": r.y0,
                    "x0": r.x0,
                    "col": col,
                    "type": "image",
                    "bytes": img_bytes
                })

        page_elements = []

        # 收集文本元素
        for b in blocks:
            x0, y0, x1, y1, text, block_no, block_type = b
            if block_type == 0:
                cleaned_text = text.strip()
                if not cleaned_text:
                    continue
                col = 0 if x0 < mid_x else 1
                page_elements.append({
                    "y0": y0,
                    "x0": x0,
                    "col": col,
                    "type": "text",
                    "content": cleaned_text
                })

        # 合并图片元素
        page_elements.extend(image_elements)

        # 双栏排序：先按左右栏 (col)，再按垂直高度 (y0)
        page_elements.sort(key=lambda e: (e["col"], e["y0"]))

        # 依次写入 Word 文档
        for elem in page_elements:
            if elem["type"] == "text":
                output_doc.add_paragraph(elem["content"])
            elif elem["type"] == "image":
                try:
                    image_stream = io.BytesIO(elem["bytes"])
                    # 在 Word 中插入图片并限定最大宽度，防止过大
                    output_doc.add_picture(image_stream, width=Inches(4.5))
                except Exception as e:
                    print(f"插入图片失败: {e}")

    # 将生成的 Word 保存到内存字节流中
    doc_io = io.BytesIO()
    output_doc.save(doc_io)
    doc_io.seek(0)
    return doc_io
