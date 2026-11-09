# app.py
import os
import streamlit as st
import requests
from utils.pdf_parser import extract_structured_content
from utils.translator import translate_chunk
from utils.glossary_loader import load_glossary_from_csv, get_dynamic_glossary_prompt

st.set_page_config(
    page_title="麻醉学文献智能翻译系统 (Markdown版)",
    page_icon="📖",
    layout="wide"
)

# 获取模型列表失败时使用的备用模型
FALLBACK_FREE_MODELS = [
    {"id": "nvidia/nemotron-3-super-120b-a12b:free", "name": "Nemotron 3 Super 120B", "context_length": 0},
    {"id": "qwen/qwen3.8-27b:free", "name": "Qwen 3.8 27B", "context_length": 0},
    {"id": "google/gemma-4-31b-it:free", "name": "Gemma 4 31B IT", "context_length": 0},
    {"id": "apodex/apodex-1.1-mini:free", "name": "Apodex 1.1 Mini", "context_length": 0},
]


def load_api_key() -> str:
    """在后台读取 API Key：优先 st.secrets，其次环境变量。不在界面上显示。"""
    names = ("OPENAI_API_KEY", "OPENROUTER_API_KEY", "DEEPSEEK_API_KEY")
    try:
        for n in names:
            if n in st.secrets and st.secrets[n]:
                return str(st.secrets[n])
    except Exception:
        pass  # 未配置 secrets.toml 时会抛异常，忽略并回退到环境变量
    for n in names:
        if os.environ.get(n):
            return os.environ[n]
    return ""


def _is_free(model: dict) -> bool:
    """判断是否为免费模型：ID 以 :free 结尾，或 prompt/completion 单价均为 0。"""
    if model.get("id", "").endswith(":free"):
        return True
    pricing = model.get("pricing") or {}
    try:
        return float(pricing.get("prompt", 1)) == 0 and float(pricing.get("completion", 1)) == 0
    except (TypeError, ValueError):
        return False


def _outputs_text(model: dict) -> bool:
    """只保留输出文本的模型（排除纯图像/音频生成模型）。"""
    arch = model.get("architecture") or {}
    outs = arch.get("output_modalities")
    return True if not outs else "text" in outs


@st.cache_data(ttl=300, show_spinner=False)
def fetch_openrouter_models(base_url: str, only_free: bool = True):
    """
    实时从 OpenRouter 拉取模型列表（该接口无需 API Key），缓存 5 分钟。
    返回 (模型列表, 错误信息)；失败时模型列表为空。
    """
    try:
        resp = requests.get(f"{base_url.rstrip('/')}/models", timeout=15)
        resp.raise_for_status()
        data = resp.json().get("data", [])
    except Exception as e:
        return [], str(e)

    models = []
    for m in data:
        if not _outputs_text(m):
            continue
        if only_free and not _is_free(m):
            continue
        models.append({
            "id": m["id"],
            "name": m.get("name", m["id"]),
            "context_length": m.get("context_length") or 0,
        })
    # 按上下文长度从大到小排序，其次按名称
    models.sort(key=lambda x: (-x["context_length"], x["name"]))
    return models, None


def _format_model(m: dict) -> str:
    ctx = f" · {m['context_length'] // 1000}K" if m.get("context_length") else ""
    return f"{m['name']}{ctx}  [{m['id']}]"


st.title("📖 麻醉学专业文档智能翻译系统 (Markdown 高效版)")
st.markdown("支持上传 **PDF、Word、Markdown、TXT** 格式文献，结合专业术语库，输出高质量的结构化 Markdown 双语翻译。")

# 加载专业词典（loader 会自动优先寻找并解析 glossary.md）
glossary_df = load_glossary_from_csv("glossary.md")
if glossary_df is not None:
    st.sidebar.success(f"✅ 专业词典加载成功（共收录 {len(glossary_df)} 条核心术语）")
else:
    st.sidebar.warning("⚠️ 未检测到词典，将进行纯大模型翻译。")

with st.sidebar:
    st.header("⚙️ 配置面板")
    backend_key = load_api_key()
    manual_key = st.text_input(
        "API Key（可选，手动输入优先于后台配置）",
        value="",
        type="password",
        placeholder="留空则使用后台配置的 Key",
    ).strip()

    if manual_key:
        api_key = manual_key
        st.info("🔑 正在使用手动输入的 API Key")
    elif backend_key:
        api_key = backend_key
        st.success("🔑 已使用后台配置的 API Key")
    else:
        api_key = ""
        st.error("❌ 未检测到后台 API Key，请在上方手动输入，或在 .streamlit/secrets.toml / 环境变量中配置")
    base_url = st.text_input("API Base URL", value="https://openrouter.ai/api/v1")

    is_openrouter = "openrouter.ai" in base_url.lower()

    if is_openrouter:
        col_a, col_b = st.columns([3, 2])
        with col_a:
            only_free = st.checkbox("仅显示免费模型", value=True)
        with col_b:
            if st.button("🔄 刷新", help="重新从 OpenRouter 获取最新模型列表"):
                fetch_openrouter_models.clear()

        with st.spinner("正在获取 OpenRouter 模型列表..."):
            models, fetch_error = fetch_openrouter_models(base_url, only_free)

        if fetch_error or not models:
            st.warning(
                f"⚠️ 无法实时获取模型列表（{fetch_error or '列表为空'}），已使用内置备用列表。"
            )
            models = FALLBACK_FREE_MODELS
        else:
            st.caption(f"🟢 已实时加载 {len(models)} 个{'免费' if only_free else ''}模型")

        model_name = st.selectbox(
            "选择翻译大模型",
            options=[m["id"] for m in models],
            format_func=lambda mid: _format_model(next(m for m in models if m["id"] == mid)),
            index=0,
        )
        custom_model = st.text_input("或手动输入模型 ID（可选，优先生效）", value="")
        if custom_model.strip():
            model_name = custom_model.strip()
    else:
        # 非 OpenRouter（如 DeepSeek 等）无法使用该接口，改为手动输入
        model_name = st.text_input("模型名称", value="deepseek-chat")

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
            st.error("未检测到 API Key，请在侧边栏手动输入，或在后台（secrets.toml / 环境变量）配置。")
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
                status_text.text(f"正在翻译第 {idx + 1} / {total_chunks} 个文本块...（模型：{model_name}）")

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
