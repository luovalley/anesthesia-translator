import os
import pandas as pd

def load_glossary_from_csv():
    """
    自动加载同级目录下的麻醉学双语词典
    """
    csv_path = "anesthesia_glossary.csv"
    if os.path.exists(csv_path):
        try:
            return pd.read_csv(csv_path)
        except Exception:
            return None
    return None

def get_dynamic_glossary_prompt(text_chunk, glossary_df, max_terms=30):
    if glossary_df is None or glossary_df.empty:
        return ""
    
    matched_terms = []
    text_lower = text_chunk.lower()
    
    for _, row in glossary_df.iterrows():
        eng = str(row.get("English", "")).lower()
        if eng and eng in text_lower:
            abbrev = str(row.get("Abbreviation", ""))
            abbrev_str = f" ({abbrev})" if abbrev and abbrev != "nan" else ""
            matched_terms.append(f"- {row['English']}{abbrev_str}: {row['Chinese']}")
            
    if len(matched_terms) < 5:
        for _, row in glossary_df.head(15).iterrows():
            abbrev = str(row.get("Abbreviation", ""))
            abbrev_str = f" ({abbrev})" if abbrev and abbrev != "nan" else ""
            term_str = f"- {row['English']}{abbrev_str}: {row['Chinese']}"
            if term_str not in matched_terms:
                matched_terms.append(term_str)
                
    selected_terms = matched_terms[:max_terms]
    return "请严格遵循以下麻醉学专业中英文对照标准进行翻译：\n" + "\n".join(selected_terms)