# utils/translator.py
import time
from openai import OpenAI
from openai import RateLimitError, APIError
import requests

def translate_chunk(text_chunk, api_key, base_url, model_name, glossary_prompt="", request_delay=3.0):
    """
    调用 OpenRouter/DeepSeek 等大模型 API 进行专业翻译。
    内置规则：遇到英文参考文献、文献引用标号或出处信息时，保持英文原文不翻译。
    """
    system_prompt = (
        "你是一个顶级的医学与麻醉学专业翻译引擎。请将输入的英文文献段落翻译为符合中国国家标准的专业中文医学学术语言。\n"
        "【核心翻译规则】\n"
        "1. 术语对齐：严格遵循提供的专业术语对照。\n"
        "2. **参考文献不翻译**：如果文本块属于参考文献列表（References）、带有期刊名称、卷期页码、作者列表以及密集的文献引用编号（例如形如 '17,23', 'Clin J Pain 2021; 37: 12-20' 等），**请直接保留英文原文，不要将其翻译成中文**。\n"
        "3. 保持 Markdown 格式与段落结构不变。"
    )
    
    user_content = f"{glossary_prompt}\n\n【待翻译英文文本】：\n{text_chunk}"
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/anesthesia-translator", 
        "X-Title": "Anesthesia Translator"
    }
    
    payload = {
        "model": model_name,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content}
        ],
        "temperature": 0.1
    }
    
    # 控制请求间隔，防止触发 API 频率限制
    time.sleep(request_delay)
    
    try:
        response = requests.post(f"{base_url.rstrip('/')}/chat/completions", headers=headers, json=payload, timeout=60)
        if response.status_code == 200:
            res_json = response.json()
            return res_json["choices"][0]["message"]["content"].strip()
        else:
            raise Exception(f"API 请求失败 [状态码 {response.status_code}]: {response.text}")
    except Exception as e:
        raise Exception(f"翻译大模型调用异常: {str(e)}")

def translate_chunk(text_chunk, api_key, base_url, model_name, glossary_prompt="", request_delay=3.0):
    """
    调用大模型进行医学翻译，包含针对免费模型的频率限制保护与自动重试机制
    """
    client = OpenAI(api_key=api_key, base_url=base_url)
    
    system_prompt = (
        "你是一个资深的麻醉学专家和医学翻译。请将以下英文麻醉学教材段落翻译为严谨、流畅、符合中文医学出版标准的简体中文。\n"
        "要求：\n"
        "1. 严格保留原有的 Markdown 结构（如标题 #, ##, 列表 *, 表格等）。\n"
        "2. 专业术语（如 Eleveld 模型、MAC、肌松药、血流动力学等）必须准确使用国内医学界标准译名。\n"
        "3. 保持客观、严谨的学术语气，不增删核心临床数据。\n"
    )
    
    if glossary_prompt:
        system_prompt += f"\n{glossary_prompt}\n"

    max_retries = 5
    backoff_factor = 3  # 递增重试等待时间（秒）

    for attempt in range(max_retries):
        try:
            response = client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": text_chunk}
                ],
                temperature=0.2,
            )
            
            # 每次成功请求后强制缓冲指定的秒数，避免触发免费模型的 RPM 限制
            time.sleep(request_delay)
            return response.choices[0].message.content
            
        except (RateLimitError, APIError) as e:
            # 针对 429 频率限制或服务器繁忙进行智能退避重试
            wait_time = backoff_factor * (2 ** attempt)
            if attempt == max_retries - 1:
                raise Exception(f"达到最大重试次数仍失败。错误信息: {str(e)}")
            time.sleep(wait_time)
        except Exception as e:
            raise e
