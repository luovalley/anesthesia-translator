# utils/pdf_parser.py
import fitz  # PyMuPDF
import os
from docx import Document

def extract_text_and_images_from_pdf(uploaded_file, start_page=1, end_page=1, image_output_dir="extracted_images"):
    """
    高级 PDF 解析器：提取文本、保持版面顺序、提取并保存图片，实现图文混排的 Markdown 转换
    """
    os.makedirs(image_output_dir, exist_ok=True)
    doc = fitz.open(stream=uploaded_file.read(), filetype="pdf")
    total_pages = len(doc)
    
    start_idx = max(0, start_page - 1)
    end_idx = min(total_pages, end_page)
    
    structured_content = []
    image_counter = 0

    for page_num in range(start_idx, end_idx):
        page = doc[page_num]
        
        # 1. 获取页面所有文本块 (x0, y0, x1, y1, text, block_no, block_type)
        # block_type: 0 代表文本, 1 代表图片
        blocks = page.get_text("blocks")
        page_elements = []
        
        for b in blocks:
            x0, y0, x1, y1, text, block_no, block_type = b
            if block_type == 0 and text.strip():
                page_elements.append({
                    "y0": y0,
                    "x0": x0,
                    "type": "text",
                    "content": text.strip()
                })
                
        # 2. 获取页面中的嵌入图片及其实际位置
        image_list = page.get_images(full=True)
        for img_index, img in enumerate(image_list):
            xref = img[0]
            base_image = doc.extract_image(xref)
            image_bytes = base_image["image"]
            image_ext = base_image["ext"]
            
            # 寻找图片在页面中的坐标位置
            img_rects = page.get_image_rects(xref)
            y0 = img_rects[0].y0 if img_rects else 0.0
            x0 = img_rects[0].x0 if img_rects else 0.0
            
            image_counter += 1
            image_filename = f"page_{page_num + 1}_img_{image_counter}.{image_ext}"
            image_filepath = os.path.join(image_output_dir, image_filename)
            
            with open(image_filepath, "wb") as f:
                f.write(image_bytes)
                
            page_elements.append({
                "y0": y0,
                "x0": x0,
                "type": "image",
                "content": f"\n\n![Figure {image_counter}]({image_output_dir}/{image_filename})\n\n"
            })
            
        # 3. 按照垂直坐标 (y0) 从上到下、水平坐标 (x0) 从左到右对图文元素进行精确排序
        page_elements.sort(key=lambda e: (e["y0"], e["x0"]))
        
        page_text_combined = "\n\n".join([elem["content"] for elem in page_elements])
        structured_content.append(f"<!-- Page {page_num + 1} -->\n\n" + page_text_combined)
        
    full_structured_text = "\n\n---\n\n".join(structured_content)
    return full_structured_text, total_pages


def extract_text_from_file(uploaded_file, start_page=1, end_page=1):
    """
    兼容原有其他格式文件读取的封装函数
    """
    file_extension = uploaded_file.name.split('.')[-1].lower()
    
    if file_extension == 'pdf':
        return extract_text_and_images_from_pdf(uploaded_file, start_page, end_page)
    elif file_extension in ['md', 'txt']:
        bytes_data = uploaded_file.read()
        for encoding in ['utf-8', 'gbk', 'latin-1']:
            try:
                return bytes_data.decode(encoding), 1
            except UnicodeDecodeError:
                continue
        return "", 1
    elif file_extension == 'docx':
        doc = Document(uploaded_file)
        paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
        return "\n\n".join(paragraphs), 1
    else:
        raise ValueError(f"不支持的文件格式: .{file_extension}")