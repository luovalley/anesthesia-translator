# app.py
import streamlit as st
import os
from utils.pdf_parser import extract_text_from_file
from utils.translator import translate_chunk
from utils.glossary_loader import load_glossary_from_csv, get_dynamic_glossary_prompt

# 页面基础配置
st.set_page_config(
    page_title="麻醉学教材多格式文档智能翻译系统",
    page_icon="📖",
    layout="wide"
)

st.title("📖 麻醉学专业文档 Markdown 智能翻译系统")
st.markdown("支持上传 **PDF（自动保持图文排版与图片提取）、Word (.docx)、Markdown (.md)、TXT** 格式的教材与文献，结合内置麻醉学专业术语库进行高质量学术翻译。")

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

# 文件上传组件（支持 PDF、Word、Markdown、TXT）
uploaded_file = st.file_uploader("请上传英文麻醉学教材或文档", type=["pdf", "md", "docx", "txt"])

if uploaded_file is not None:
    uploaded_file.seek(0)
    file_extension = uploaded_file.name.split('.')[-1].lower()
    
    with st.spinner("正在解析文档内容及图文混排结构..."):
        doc_io, total_units = extract_text_from_file(uploaded_file, start_page=start_page, end_page=end_page)
        
    st.info(f"📄 成功生成排版規整、内嵌图片的 Word 文档！预估处理单元: {total_units}")
    
    # 针对 PDF 允许选页，如果是其他文档则直接全文分块
    start_page, end_page = 1, 1
    if file_extension == 'pdf':
        col1, col2 = st.columns(2)
        with col1:
            start_page = st.number_input("起始页码", min_value=1, max_value=total_units, value=1)
        with col2:
            end_page = st.number_input("结束页码", min_value=1, max_value=total_units, value=min(10, total_units))
            
    if st.button("🚀 开始智能翻译", type="primary"):
        if not api_key:
            st.error("请先在左侧侧边栏输入有效的 API Key！")
        else:
            uploaded_file.seek(0)
            # 如果是 PDF，按用户选择的页码重新提取图文混排结构
            if file_extension == 'pdf':
                target_text, _ = extract_text_from_file(uploaded_file, start_page=start_page, end_page=end_page)
            else:
                target_text = full_text
            
            # 按字符数分块处理大文本
            chunks = [target_text[i:i + chunk_size] for i in range(0, len(target_text), chunk_size)]
            
            translated_result = []
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            total_chunks = len(chunks)
            
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
                
            status_text.text("✨ 翻译全部完成！")
            final_markdown = "\n\n".join(translated_result)
            
            st.subheader("📋 翻译结果预览 (Markdown 包含图文排版)")
            st.markdown(final_markdown, unsafe_allow_html=True)
            
            st.download_button(
                label="📥 下载排版完美的 Word 文档 (.docx)",
                data=target_doc_io,
                file_name=f"{uploaded_file.name}_translated.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            )
