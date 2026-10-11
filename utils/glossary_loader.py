# utils/glossary_loader.py
import os
import pandas as pd

def load_glossary(file_path="glossary.md"):
    """
    通用术语表加载函数，完美支持列表格式 (如 * English — Chinese) 
    以及 Markdown 表格和键值对格式。
    """
    if not os.path.exists(file_path):
        fallback = "anesthesia_glossary.csv"
        if os.path.exists(fallback):
            file_path = fallback
        else:
            return None
            
    terms = []
    file_extension = file_path.split(".")[-1].lower()
    
    try:
        if file_extension == "md":
            with open(file_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
                
            for line in lines:
                line = line.strip()
                
                # 1. 适配你当前的格式：* Abdomen — 腹部 或 * Term - 翻译
                if line.startswith("*") or line.startswith("-"):
                    # 去除前缀的符号和空格
                    content = line.lstrip("*-# ").strip()
                    # 尝试用常用的中英文分隔符（如 — 或 -）进行切分
                    for sep in ["—", "–", "-"]:
                        if sep in content:
                            parts = content.split(sep, 1)
                            en = parts[0].strip()
                            zh = parts[1].strip()
                            if en and zh:
                                terms.append({"English": en, "Chinese": zh})
                            break
                            
                # 2. 兼容 Markdown 表格格式：| English | Chinese |
                elif line.startswith("|") and line.endswith("|"):
                    parts = [p.strip() for p in line.split("|")[1:-1]]
                    if len(parts) >= 2 and not all(set(p) <= {"-", ":"} for p in parts):
                        en, zh = parts[0], parts[1]
                        if en and zh and en.lower() != "english" and en.lower() != "术语":
                            terms.append({"English": en, "Chinese": zh})
                            
                # 3. 兼容冒号格式：English: 中文
                elif ":" in line:
                    parts = line.lstrip("-*# ").split(":", 1)
                    if len(parts) == 2:
                        en, zh = parts[0].strip(), parts[1].strip()
                        if en and zh:
                            terms.append({"English": en, "Chinese": zh})
                            
            if terms:
                return pd.DataFrame(terms)
                
        elif file_extension == "csv":
            return pd.read_csv(file_path)
            
    except Exception as e:
        print(f"加载词典文件 {file_path} 出错: {e}")
        
    return None

def load_glossary_from_csv(file_path="anesthesia_glossary.csv"):
    if os.path.exists("glossary.md"):
        return load_glossary("glossary.md")
    return load_glossary(file_path)

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
            matched_terms.append(f"- {en_term} => {zh_term}")
            
    if not matched_terms:
        return ""
        
    prompt_snippet = "【专业术语对齐参考】\n请在翻译本段时严格遵循以下麻醉学专业术语对照：\n" + "\n".join(matched_terms[:30])
    return prompt_snippet
