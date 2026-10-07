# app.py
import streamlit as st
import os
import io
import docx
from docx.shared import Inches
from utils.pdf_parser import extract_structured_content
from utils.translator import translate_chunk
from utils.glossary_loader import load_glossary_from_csv, get_dynamic_glossary_prompt

st.set_page_config(
    page_title="麻醉学教材多格式文档智能翻译系统",
    page_icon="📖",
    layout="wide"
)

st.title("📖 麻醉学专业文档智能翻译系统 (结构化图文混排版)")
st.markdown("支持上传 **PDF（自动保持双栏图文排版与图片提取）**，采用结构化映射机制确保图文100%不丢失、不乱码。")

glossary_df = load_glossary_from_csv()
if glossary_df is not None:
    st.sidebar.success(f"✅ 专业词典加载成功（共收录 {len(glossary_df)} 条核心术语）")
else:
    st.sidebar.warning("⚠️ 未检测到词典，将进行纯大模型翻译。")

with st.sidebar:
    st.header("⚙️ 配置面板")
    default_api_key = st.secrets.get("OPENAI_API_KEY", "") if "OPENAI_API_KEY" in st.secrets else ""
    api_key = st.text_input("API Key (OpenRouter / DeepSeek)", value=default_api_key, type="password")
    base_url = st.text_input("API Base URL", value="https://openrouter.ai/api/v1")
    model_name = st.selectbox(
        "选择翻译大模型", 
        [
            "nvidia/nemotron-3-super-120b-a12b:free",
            "qwen/qwen3.8-27b:free", 
            "google/gemma-4-31b-it:free", 
            "apodex/apodex-1.1-mini:free",
        ],
        index=0
    )
    st.divider()
    enable_glossary = st.checkbox("启用麻醉学专业术语动态对齐", value=True)
    chunk_size = st.slider("单次文本分块字符数", min_value=2000, max_value=8000, value=3500, step=500)
    request_delay = st.slider("API 请求安全间隔 (秒)", min_value=1.0, max_value=10.0, value=3.0, step=0.5)

uploaded_file = st.file_uploader("请上传英文麻醉学教材或 PDF", type=["pdf", "md", "docx", "txt"])

if uploaded_file is not None:
    uploaded_file.seek(0)
    file_extension = uploaded_file.name.split('.')[-1].lower()
    
    start_page, end_page = 1, 10
    
    # 预解析获取总页数
    with st.spinner("正在解析文档结构..."):
        _, total_units = extract_structured_content(uploaded_file, start_page=1, end_page=None)
    
    if file_extension == 'pdf':
        st.sidebar.markdown("---")
        st.sidebar.subheader("📄 PDF 页码范围设置")
        col1, col2 = st.sidebar.columns(2)
        with col1:
            start_page = st.number_input("起始页码", min_value=1, value=1)
        with col2:
            end_page = st.number_input("结束页码", min_value=1, value=min(10, total_units))

    st.info(f"📄 成功解析文档！总页数/单元: {total_units}")
    
    if st.button("🚀 开始智能翻译并生成图文排版 Word", type="primary"):
        if not api_key:
            st.error("请先在左侧侧边栏输入有效的 API Key！")
        else:
            uploaded_file.seek(0)
            
            with st.spinner("正在提取结构化图文数据..."):
                elements, _ = extract_structured_content(uploaded_file, start_page=start_page, end_page=end_page)
            
            # 提取所有纯文本元素进行拼接与分块，同时记录文本在 elements 中的索引映射
            text_items = [el for el in elements if el["type"] == "text"]
            combined_text = "\n".join([item["content"] for item in text_items])
            
            chunks = [combined_text[i:i + chunk_size] for i in range(0, len(combined_text), chunk_size)]
            
            translated_chunks = []
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            total_chunks = len(chunks) if chunks else 1
            if not chunks:
                chunks = [combined_text]
            
            for idx, chunk in enumerate(chunks):
                status_text.text(f"正在翻译第 {idx + 1} / {total_chunks} 个文本块...")
                
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
                    translated_chunks.append(translated_chunk)
                except Exception as e:
                    st.error(f"第 {idx + 1} 块翻译出错: {str(e)}")
                    break
                
                progress_bar.progress((idx + 1) / total_chunks)
                
            status_text.text("✨ 翻译完成，正在组装图文混排 Word 文档...")
            
            full_translated_text = "\n".join(translated_chunks)
            
            # 生成最终 Word 文档
            final_doc = docx.Document()
            
            # 按顺序将翻译文本与图片重新组合写入 Word
            # 遍历结构化 elements：如果是图片，直接插入；如果是文本，按行写入翻译内容
            translated_lines = full_translated_text.split("\n")
            line_idx = 0
            
            for el in elements:
                if el["type"] == "image":
                    try:
                        img_stream = io.BytesIO(el["data"])
                        final_doc.add_picture(img_stream, width=Inches(4.5))
                    except Exception:
                        final_doc.add_paragraph("[图片嵌入失败]")
                elif el["type"] == "text":
                    # 写入对应的翻译文本行
                    if line_idx < len(translated_lines):
                        line_text = translated_lines[line_idx].strip()
                        if line_text:
                            final_doc.add_paragraph(line_text)
                        line_idx += 1
            
            translated_doc_io = io.BytesIO()
            final_doc.save(translated_doc_io)
            translated_doc_io.seek(0)
            
            status_text.text("✅ 图文混排 Word 生成完毕！")
            
            st.subheader("📋 翻译结果预览")
            st.markdown(full_translated_text, unsafe_allow_html=True)
            
            st.download_button(
                label="📥 下载完美图文排版 Word 文档 (.docx)",
                data=translated_doc_io,
                file_name=f"{uploaded_file.name}_translated_perfect.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            )
else:
    st.info("👈 请在上方上传需要处理的 PDF 文档。")
