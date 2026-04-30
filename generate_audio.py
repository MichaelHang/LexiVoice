import asyncio
import edge_tts
import os
import requests
from pydub import AudioSegment

# --- Configuration ---
OUTPUT_DIR = "SpellEcho_Files"
VOICE = "en-US-AvaNeural"

def get_youdao_translation(word):
    """Get Chinese translation via Youdao API"""
    try:
        url = f"https://dict.youdao.com/suggest?q={word}&num=1&doctype=json"
        response = requests.get(url, timeout=5)
        data = response.json()
        # Extract translation: usually take the first explanation of first match
        explanation = data['data']['entries'][0]['explain']
        print(f"Translation for '{word}': {explanation}")
        # Clean translation: only keep Chinese part, filter out possible part-of-speech tags
        clean_cn = explanation.split('，')[0].split('.')[-1].strip()
        print(f"Cleaned translation: {clean_cn}")
        return clean_cn
    except Exception as e:
        print(f"Translation failed for '{word}' (check network): {e}")
        return ""

async def generate_segment(text, filename):
    communicate = edge_tts.Communicate(text, VOICE)
    await communicate.save(filename)
    return AudioSegment.from_mp3(filename)

async def process_word(word_en, pause_1s, pause_2s):
    # 1. Get Chinese translation
    word_cn = get_youdao_translation(word_en)
    # Handle case when translation is empty
    safe_cn = "".join(x for x in word_cn if x.isalnum()) # Ensure filename is legal
    full_name = f"{word_en}{safe_cn}"
    print(f"Processing: {word_en}")

    temp_file = f"temp_{word_en}.mp3"
    combined = AudioSegment.empty()

    try:
        # 2. Generate speech audio
        word_audio = await generate_segment(word_en, temp_file)
        combined += word_audio + pause_2s

        # 3. Spell out letter by letter
        for char in word_en:
            if char.isalpha():
                char_audio = await generate_segment(char, "temp_char.mp3")
                combined += char_audio + pause_1s

        # 4. Read the word again
        combined += word_audio + pause_2s

        # 5. Export file
        output_path = os.path.join(OUTPUT_DIR, f"{full_name}.mp3")
        combined.export(output_path, format="mp3")

    finally:
        for f in [temp_file, "temp_char.mp3"]:
            if os.path.exists(f): os.remove(f)

async def main():
    if not os.path.exists(OUTPUT_DIR): os.makedirs(OUTPUT_DIR)
    if not os.path.exists("words.txt"):
        print("Error: words.txt not found. Please create it and write English words in it.")
        return

    with open("words.txt", 'r', encoding='utf-8') as f:
        content = f.read().strip()

    word_list = [w.strip() for w in (content.split(',') if ',' in content else content.splitlines()) if w.strip()]

    pause_1s = AudioSegment.silent(duration=300)
    pause_2s = AudioSegment.silent(duration=2000)

    print(f"Detected {len(word_list)} words, processing with Youdao translation...")
    for word in word_list:
        await process_word(word, pause_1s, pause_2s)

    print(f"\nDone! Audio files saved in '{OUTPUT_DIR}' folder.")

if __name__ == "__main__":
    asyncio.run(main())