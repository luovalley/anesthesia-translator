import os
import fitz  # PyMuPDF
import docx

def extract_text_from_file(uploaded_file, start_page=1, end_page=None):
    """
    适配 app.py 调用的统一入口，支持指定页码范围解析
    """
    file_name = uploaded_file.name
    file_extension = file_name.split(".")[-1].lower()
    
    if file_extension == "pdf":
        pdf_bytes = uploaded_file.read()
        text = parse_pdf_with_layout(pdf_bytes, start_page=start_page, end_page=end_page)
    elif file_extension in ["docx", "doc"]:
        doc = docx.Document(uploaded_file)
        text = "\n".join([p.text for p in doc.paragraphs])
    elif file_extension in ["md", "txt"]:
        text = uploaded_file.read().decode("utf-8")
    else:
        text = "不支持的文件格式。"
        
    total_units = len(text)
    return text, total_units

def parse_pdf_with_layout(pdf_bytes, output_image_dir="extracted_images", start_page=1, end_page=None):
    """
    针对双栏医学文献优化的 PDF 坐标块与图文混排解析器（支持页码范围）
    """
    os.makedirs(output_image_dir, exist_ok=True)
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    full_markdown_content = []

    total_pages = len(doc)
    # 处理页码索引（用户输入的页码从 1 开始，转换为从 0 开始的索引）
    start_idx = max(0, start_page - 1)
    end_idx = min(total_pages, end_page) if end_page else total_pages

    for page_num in range(start_idx, end_idx):
        page = doc[page_num]
        full_markdown_content.append(f"\n\n<!-- Page {page_num + 1} -->\n")
        
        page_width = page.rect.width
        mid_x = page_width / 2.0

        blocks = page.get_text("blocks", sort=True)
        
        image_list = page.get_images(full=True)
        image_rects = []
        for img_index, img_info in enumerate(image_list):
            xref = img_info[0]
            rects = page.get_image_rects(xref)
            for r in rects:
                pix = fitz.Pixmap(doc, xref)
                if pix.n >= 5:
                    pix = fitz.Pixmap(fitz.csRGB, pix)
                img_filename = f"page_{page_num + 1}_img_{xref}_{img_index}.png"
                img_path = os.path.join(output_image_dir, img_filename)
                pix.save(img_path)
                pix = None
                
                image_rects.append({
                    "y0": r.y0,
                    "x0": r.x0,
                    "y1": r.y1,
                    "path": img_path
                })

        page_elements = []

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

        for img in image_rects:
            col = 0 if img["x0"] < mid_x else 1
            img_markdown = f"\n\n![Figure]({img['path']})\n\n"
            page_elements.append({
                "y0": img["y0"],
                "x0": img["x0"],
                "col": col,
                "type": "image",
                "content": img_markdown
            })

        page_elements.sort(key=lambda e: (e["col"], e["y0"]))
        page_text_blocks = [elem["content"] for elem in page_elements]
        full_markdown_content.extend(page_text_blocks)

    return "\n\n".join(full_markdown_content)
