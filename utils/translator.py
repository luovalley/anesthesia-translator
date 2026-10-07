# utils/translator.py
import time
from openai import OpenAI
from openai import RateLimitError, APIError

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