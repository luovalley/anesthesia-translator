# utils/glossary_loader.py
import os
import re
import pandas as pd

def load_glossary_from_md(file_path="glossary.md"):
    """
    从 Markdown 文件中加载麻醉学专业术语表。
    支持标准的 Markdown 表格格式，例如：
    | English Term | 中文翻译 | 或类似结构
    或者支持列表/键值对格式。
    """
    if not os.path.exists(file_path):
        return None
    
    terms = []
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
            
        for line in lines:
            line = line.strip()
            # 匹配 Markdown 表格行，例如 | Propofol | 丙泊酚 |
            if line.startswith("|") and line.endswith("|"):
                parts = [p.strip() for p in line.split("|")[1:-1]]
                # 过滤掉表头分隔符行（如 --- | ---）
                if len(parts) >= 2 and not all(set(p) <= {"-", ":"} for p in parts):
                    en, zh = parts[0], parts[1]
                    if en and zh and en.lower() != "english" and en.lower() != "术语":
                        terms.append({"English": en, "Chinese": zh})
            
            # 兼容其他常见格式，例如：- Propofol: 丙泊酚 或 **Propofol** - 丙泊酚
            elif ":" in line or "-" in line:
                # 简单清洗并尝试提取
                cleaned = line.lstrip("-*# ").strip()
                if ":" in cleaned:
                    parts = cleaned.split(":", 1)
                    terms.append({"English": parts[0].strip(), "Chinese": parts[1].strip()})
                    
        if terms:
            return pd.DataFrame(terms)
    except Exception as e:
        print(f"加载 glossary.md 出错: {e}")
        
    return None

def load_glossary_from_csv(file_path="anesthesia_glossary.csv"):
    """
    兼容旧的 CSV 格式，如果 md 不存在或为空时作为后备
    """
    md_df = load_glossary_from_md("glossary.md")
    if md_df is not None and not md_df.empty:
        return md_df
        
    if os.path.exists(file_path):
        try:
            return pd.read_csv(file_path)
        except Exception:
            return None
    return None

def get_dynamic_glossary_prompt(text_chunk, glossary_df):
    """
    根据当前文本块的内容，动态筛选出其中包含的专业术语，拼接到 Prompt 中
    """
    if glossary_df is None or glossary_df.empty:
        return ""
        
    matched_terms = []
    text_lower = text_chunk.lower()
    
    for _, row in glossary_df.iterrows():
        en_term = str(row.get("English", ""))
        zh_term = str(row.get("Chinese", ""))
        
        if en_term and en_term.lower() in text_lower:
            matched_terms.append(-f"- {en_term} => {zh_term}")
            
    if not matched_terms:
        # 如果没有精确匹配到，随机或取前部分核心术语作为参考，或者返回空
        return ""
        
    prompt_snippet = "【专业术语对齐参考】\n请在翻译本段时严格遵循以下麻醉学专业术语对照：\n" + "\n".join(matched_terms[:30])
    return prompt_snippet
