# app.py
import streamlit as st
import os
import io
from utils.pdf_parser import extract_structured_content
from utils.translator import translate_chunk
from utils.glossary_loader import load_glossary_from_csv, get_dynamic_glossary_prompt

st.set_page_config(
    page_title="麻醉学文献智能翻译系统 (Markdown版)",
    page_icon="📖",
    layout="wide"
)

st.title("📖 麻醉学专业文档智能翻译系统 (Markdown 高效版)")
st.markdown("支持上传 **PDF、Word、Markdown、TXT** 格式文献，结合专业术语库，输出高质量的结构化 Markdown 双语翻译。")

# 加载专业词典
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

uploaded_file = st.file_uploader("请上传需要翻译的医学文献或教材", type=["pdf", "md", "docx", "txt"])

if uploaded_file is not None:
    uploaded_file.seek(0)
    file_extension = uploaded_file.name.split('.')[-1].lower()
    
    start_page, end_page = 1, 10
    
    # 预解析获取总页数
    with st.spinner("正在解析文档..."):
        _, total_units = extract_structured_content(uploaded_file, start_page=1, end_page=None)
    
    if file_extension == 'pdf':
        st.sidebar.markdown("---")
        st.sidebar.subheader("📄 PDF 页码范围设置")
        col1, col2 = st.sidebar.columns(2)
        with col1:
            start_page = st.number_input("起始页码", min_value=1, value=1)
        with col2:
            end_page = st.number_input("结束页码", min_value=1, value=min(10, total_units))

    st.info(f"📄 文档解析成功！总页数/单元: {total_units}")
    
    if st.button("🚀 开始智能翻译并生成 Markdown", type="primary"):
        if not api_key:
            st.error("请先在左侧侧边栏输入有效的 API Key！")
        else:
            uploaded_file.seek(0)
            
            with st.spinner("正在提取文本内容..."):
                elements, _ = extract_structured_content(uploaded_file, start_page=start_page, end_page=end_page)
            
            # 提取所有文本块进行拼接
            text_items = [el["content"] for el in elements if el["type"] == "text"]
            combined_text = "\n".join(text_items)
            
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
                
            status_text.text("✨ 翻译完成！")
            
            full_markdown_result = "\n\n".join(translated_chunks)
            
            st.subheader("📋 翻译结果预览 (Markdown)")
            st.markdown(full_markdown_result, unsafe_allow_html=True)
            
            # 提供 Markdown 文件下载
            md_bytes = full_markdown_result.encode("utf-8")
            st.download_button(
                label="📥 下载翻译好的 Markdown 文档 (.md)",
                data=md_bytes,
                file_name=f"{uploaded_file.name}_translated.md",
                mime="text/markdown"
            )
else:
    st.info("👈 请在上方上传需要处理的文档。")
