import os
import fitz  # PyMuPDF
import docx

def extract_text_from_file(uploaded_file):
    """
    适配 app.py 调用的统一入口
    """
    # 获取文件扩展名
    file_name = uploaded_file.name
    file_extension = file_name.split(".")[-1].lower()
    
    if file_extension == "pdf":
        pdf_bytes = uploaded_file.read()
        text = parse_pdf_with_layout(pdf_bytes)
    elif file_extension in ["docx", "doc"]:
        doc = docx.Document(uploaded_file)
        text = "\n".join([p.text for p in doc.paragraphs])
    elif file_extension in ["md", "txt"]:
        text = uploaded_file.read().decode("utf-8")
    else:
        text = "不支持的文件格式。"
        
    # 估算翻译单元（例如按字符数或段落数），供 app.py 进度条使用
    total_units = len(text)
    return text, total_units

def parse_pdf_with_layout(pdf_bytes, output_image_dir="extracted_images"):
    """
    针对双栏医学文献优化的 PDF 坐标块与图文混排解析器
    """
    os.makedirs(output_image_dir, exist_ok=True)
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    full_markdown_content = []

    for page_num in range(len(doc)):
        page = doc[page_num]
        full_markdown_content.append(f"\n\n<!-- Page {page_num + 1} -->\n")
        
        page_width = page.rect.width
        mid_x = page_width / 2.0

        # 获取页面所有块 (blocks)，包含文本块和图片块
        # blocks 结构: (x0, y0, x1, y1, text/image_info, block_no, block_type)
        # block_type: 0 代表文本, 1 代表图像
        blocks = page.get_text("blocks", sort=True)
        
        # 同时提取页面中的内嵌图片及其矩形框位置
        image_list = page.get_images(full=True)
        image_rects = []
        for img_index, img_info in enumerate(image_list):
            xref = img_info[0]
            rects = page.get_image_rects(xref)
            for r in rects:
                # 保存图片到本地
                pix = fitz.Pixmap(doc, xref)
                if pix.n >= 5:  # 转换 CMYK 为 RGB
                    pix = fitz.Pixmap(fitz.csRGB, pix)
                img_filename = f"page_{page_num + 1}_img_{xref}_{img_index}.png"
                img_path = os.path.join(output_image_dir, img_filename)
                pix.save(img_path)
                pix = None
                
                # 将图片矩形与路径记录下来
                image_rects.append({
                    "y0": r.y0,
                    "x0": r.x0,
                    "y1": r.y1,
                    "path": img_path
                })

        # 整理所有需要参与排版的元素（文本块 + 图片）
        # 统一格式化为：(y0, x0, content_type, sort_column, content_string)
        page_elements = []

        # 处理文本块并进行双栏归类
        for b in blocks:
            x0, y0, x1, y1, text, block_no, block_type = b
            if block_type == 0:  # 文本
                cleaned_text = text.strip()
                if not cleaned_text:
                    continue
                # 判定属于左栏 (0) 还是右栏 (1)
                col = 0 if x0 < mid_x else 1
                page_elements.append({
                    "y0": y0,
                    "x0": x0,
                    "col": col,
                    "type": "text",
                    "content": cleaned_text
                })

        # 处理图片元素
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

        # 双栏核心排序算法：
        # 先按栏目(col: 0 -> 1)排序，再按垂直高度(y0)排序，确保双栏内容不交织混乱
        page_elements.sort(key=lambda e: (e["col"], e["y0"]))

        # 组装当前页的 Markdown
        page_text_blocks = [elem["content"] for elem in page_elements]
        full_markdown_content.extend(page_text_blocks)

    return "\n\n".join(full_markdown_content)
