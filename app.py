# app.py
import streamlit as st
import os
import io
from openai import OpenAI
from utils.pdf_parser import extract_text_from_file
from utils.translator import translate_chunk
from utils.glossary_loader import load_glossary_from_csv, get_dynamic_glossary_prompt

# ReportLab PDF 生成相关库
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image as RLImage
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# 页面基础配置
st.set_page_config(
    page_title="麻醉学教材多格式文档智能翻译系统 (PDF版)",
    page_icon="📖",
    layout="wide"
)

st.title("📖 麻醉学专业文档智能翻译系统 (PDF 图文高精度排版版)")
st.markdown("支持上传 **PDF（自动保持图文混排与图片内嵌）、Word、Markdown、TXT**，翻译后直接生成排版精美的专业学术 PDF 文档。")

# 加载本地麻醉学术语库
glossary_df = load_glossary_from_csv()
if glossary_df is not None:
    st.sidebar.success(f"✅ 专业词典加载成功（共收录 {len(glossary_df)} 条核心术语）")
else:
    st.sidebar.warning("⚠️ 未检测到 `anesthesia_glossary.csv`，将进行纯大模型翻译。")

# 侧边栏配置面板
with st.sidebar:
    st.header("⚙️ 配置面板")
    
    default_api_key = ""
    try:
        default_api_key = st.secrets.get("OPENAI_API_KEY", "")
    except Exception:
        pass
        
    api_key = st.text_input("API Key (OpenRouter / DeepSeek / OpenAI)", value=default_api_key, type="password")
    
    base_url = st.text_input(
        "API Base URL", 
        value="https://openrouter.ai/api/v1", 
        help="支持 OpenRouter、DeepSeek 官方或兼容的 OpenAI 接口"
    )
    
    model_name = st.selectbox(
        "选择翻译大模型", 
        [
            "nvidia/nemotron-3-super-120b-a12b:free",
            "qwen/qwen3.8-27b:free", 
            "google/gemma-4-31b-it:free", 
            "apodex/apodex-1.1-mini:free",
            "openrouter/free",
        ],
        index=0
    )
    
    st.divider()
    enable_glossary = st.checkbox("启用麻醉学专业术语动态对齐", value=True)
    chunk_size = st.slider("单次文本分块字符数", min_value=2000, max_value=10000, value=4000, step=500)
    
    request_delay = st.slider(
        "API 请求安全间隔 (秒)", 
        min_value=1.0, 
        max_value=10.0, 
        value=3.0, 
        step=0.5,
        help="使用免费模型时建议调大间隔（如 3-5 秒），避免并发过高导致 429 超限。"
    )

# 文件上传组件
uploaded_file = st.file_uploader("请上传英文麻醉学教材或文档", type=["pdf", "md", "docx", "txt"])

def build_pdf_from_text_and_images(text_content, image_list, output_io):
    """使用 ReportLab 生成排版精美的 PDF，支持中文与图文混排"""
    doc = SimpleDocTemplate(output_io, pagesize=letter, rightMargin=40, leftMargin=40, topMargin=40, bottomMargin=40)
    styles = getSampleStyleSheet()
    
    # 适配 Linux/Streamlit 云端常见的中文字体路径
    font_paths = [
        "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf"
    ]
    
    font_name = "Helvetica" # 默认英文字体兜底
    for path in font_paths:
        if os.path.exists(path):
            try:
                pdfmetrics.registerFont(TTFont('CustomChineseFont', path))
                font_name = 'CustomChineseFont'
                break
            except Exception:
                pass
                
    chinese_style = ParagraphStyle(
        'ChineseStyle',
        parent=styles['Normal'],
        fontName=font_name,
        fontSize=10,
        leading=14,
        spaceAfter=6
    )
    
    story = []
    image_idx = 0
    
    for line in text_content.split("\n"):
        line = line.strip()
        if "[IMAGE_EMBED]" in line:
            if image_idx < len(image_list):
                try:
                    img_stream = io.BytesIO(image_list[image_idx])
                    # 按照页面宽度自适应插入图片
                    img = RLImage(img_stream, width=400, height=250)
                    story.append(img)
                    story.append(Spacer(1, 8))
                    image_idx += 1
                except Exception:
                    story.append(Paragraph("[图片渲染失败]", chinese_style))
        elif line:
            # 替换 HTML 特殊字符防止解析报错
            safe_line = line.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            story.append(Paragraph(safe_line, chinese_style))
            
    doc.build(story)

if uploaded_file is not None:
    uploaded_file.seek(0)
    file_extension = uploaded_file.name.split('.')[-1].lower()
    
    start_page, end_page = 1, 10
    
    with st.spinner("正在解析文档结构及图文位置..."):
        _, _, total_units = extract_text_from_file(uploaded_file, start_page=1, end_page=None)
    
    if file_extension == 'pdf':
        st.sidebar.markdown("---")
        st.sidebar.subheader("📄 PDF 页码范围设置")
        col1, col2 = st.sidebar.columns(2)
        with col1:
            start_page = st.number_input("起始页码", min_value=1, value=1)
        with col2:
            end_page = st.number_input("结束页码", min_value=1, value=min(10, total_units))

    st.info(f"📄 成功解析文档！预估总页数/单元: {total_units}")
    
    if st.button("🚀 开始智能翻译并生成图文排版 PDF", type="primary"):
        if not api_key:
            st.error("请先在左侧侧边栏输入有效的 API Key！")
        else:
            uploaded_file.seek(0)
            
            with st.spinner("正在提取图文混排数据..."):
                target_text, image_list, _ = extract_text_from_file(uploaded_file, start_page=start_page, end_page=end_page)
            
            chunks = [target_text[i:i + chunk_size] for i in range(0, len(target_text), chunk_size)]
            
            translated_result = []
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            total_chunks = len(chunks)
            if total_chunks == 0:
                total_chunks = 1
                chunks = [target_text]
            
            for idx, chunk in enumerate(chunks):
                status_text.text(f"正在翻译第 {idx + 1} / {total_chunks} 个文本块（已包含限速缓冲）...")
                
                glossary_prompt = ""
                if enable_glossary and glossary_df is not None:
                    glossary_prompt = get_dynamic_glossary_prompt(chunk, glossary_df)
                
                try:
                    translated_chunk = translate_chunk(
                        text_chunk=chunk,
                        api_key=api_key,
                        base_url=base_url,
                        model_name=model_name,
                        glossary_prompt=glossary_prompt,
                        request_delay=request_delay
                    )
                    translated_result.append(translated_chunk)
                except Exception as e:
                    st.error(f"第 {idx + 1} 块翻译出错: {str(e)}")
                    break
                
                progress_bar.progress((idx + 1) / total_chunks)
                
            status_text.text("✨ 翻译完成，正在通过 ReportLab 渲染精美 PDF 文档...")
            
            final_markdown = "\n\n".join(translated_result)
            
            # 生成 PDF 内存流
            pdf_output_io = io.BytesIO()
            build_pdf_from_text_and_images(final_markdown, image_list, pdf_output_io)
            pdf_output_io.seek(0)
            
            status_text.text("✅ 图文混排 PDF 讲义生成完毕！")
            
            st.subheader("📋 翻译结果预览 (Markdown 格式)")
            st.markdown(final_markdown, unsafe_allow_html=True)
            
            st.download_button(
                label="📥 下载排版完美的 PDF 文档 (.pdf)",
                data=pdf_output_io,
                file_name=f"{uploaded_file.name}_translated_layout.pdf",
                mime="application/pdf"
            )
else:
    st.info("👈 请在上方上传需要处理的医学文献或教材文件。")
