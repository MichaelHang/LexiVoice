"""
LexiVoice Web API - 单词音频生成服务
"""
import os
import zipfile
import asyncio
import edge_tts
import requests
from flask import Flask, render_template, request, jsonify, send_file
from pydub import AudioSegment
from werkzeug.utils import secure_filename
import uuid
import shutil

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024  # 5MB max file size
app.config['OUTPUT_DIR'] = 'generated_audio'
app.config['TEMP_DIR'] = 'temp_files'

# Ensure directories exist
os.makedirs(app.config['OUTPUT_DIR'], exist_ok=True)
os.makedirs(app.config['TEMP_DIR'], exist_ok=True)

# 进度存储
generation_progress = {
    'session_id': None,
    'current': 0,
    'total': 0,
    'word': '',
    'completed': False
}

VOICE = "en-US-AvaNeural"
CHINESE_VOICE = "zh-CN-XiaoxiaoNeural"

# 使用统计数据库
app.config['USAGE_DB'] = 'usage.db'
app.config['USAGE_CSV'] = 'usage_stats.csv'


def update_usage_csv():
    """根据数据库重新生成按天聚合的 usage_stats.csv（utf-8-sig，Excel 可直接打开）"""
    import csv
    import sqlite3
    try:
        conn = sqlite3.connect(app.config['USAGE_DB'])
        rows = conn.execute(
            "SELECT day, COUNT(*) AS times, SUM(word_count) AS words "
            "FROM usage_log GROUP BY day ORDER BY day"
        ).fetchall()
        conn.close()

        total_times = sum(r[1] for r in rows)
        total_words = sum(r[2] for r in rows)

        with open(app.config['USAGE_CSV'], 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f)
            writer.writerow(['日期', '生成次数', '单词量'])
            for day, times, words in rows:
                writer.writerow([day, times, words])
            writer.writerow(['合计', total_times, total_words])
    except Exception as e:
        print(f"生成统计 CSV 失败: {e}")


def log_usage(word_count):
    """记录一次生成使用（按天统计）。使用 SQLite，线程/进程安全，并刷新 CSV。"""
    import sqlite3
    from datetime import datetime
    try:
        conn = sqlite3.connect(app.config['USAGE_DB'])
        conn.execute(
            """CREATE TABLE IF NOT EXISTS usage_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                day TEXT NOT NULL,
                word_count INTEGER NOT NULL,
                created_at TEXT NOT NULL
            )"""
        )
        conn.execute(
            "INSERT INTO usage_log (day, word_count, created_at) VALUES (?, ?, ?)",
            (datetime.now().strftime('%Y-%m-%d'), word_count, datetime.now().isoformat())
        )
        conn.commit()
        conn.close()
        update_usage_csv()
    except Exception as e:
        print(f"记录使用统计失败: {e}")



def get_youdao_translation(word, max_meanings=4):
    """获取有道翻译的中文意思，返回多个翻译"""
    try:
        url = f"https://dict.youdao.com/suggest?q={word}&num=5&doctype=json"
        response = requests.get(url, timeout=10)
        data = response.json()
        
        translations = []
        if 'data' in data and 'entries' in data['data']:
            for entry in data['data']['entries'][:max_meanings]:
                explanation = entry.get('explain', '')
                # 提取中文部分
                if any('\u4e00' <= c <= '\u9fff' for c in explanation):
                    # 清理英文词性标记
                    chinese_part = explanation.split('（')[0].split(';')[0].strip()
                    for pos in ['int.', 'n.', 'v.', 'adj.', 'adv.', 'conj.']:
                        if chinese_part.startswith(pos):
                            chinese_part = chinese_part[len(pos):].strip()
                            break
                    # 以逗号为分隔符，提取所有翻译
                    parts = chinese_part.split('，')
                    for part in parts:
                        part = part.strip().rstrip('；').rstrip(';')
                        # 过滤：纯中文、长度2-10、不含特殊符号
                        if (part and 
                            len(part) >= 2 and 
                            len(part) <= 10 and
                            not any(c in part for c in ['<', '>', '/', '=', '+', '[', ']']) and
                            part not in translations):
                            translations.append(part)
        
        return translations if translations else []
    except Exception as e:
        print(f"翻译失败: {e}")
        return []


async def generate_audio_segment(text, filename, voice=VOICE):
    """生成音频片段"""
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(filename)
    audio = AudioSegment.from_mp3(filename)
    # 统一为 24000Hz 单声道
    audio = audio.set_frame_rate(24000).set_channels(1)
    return audio


async def generate_preview_audio(letter_pause_ms, word_pause_ms, include_spelling, include_word_spelling, include_chinese):
    """生成预览音频 - 使用 'Voice' 作为示例单词"""
    session_id = str(uuid.uuid4())
    session_dir = os.path.join(app.config['OUTPUT_DIR'], session_id)
    os.makedirs(session_dir, exist_ok=True)

    preview_word = "Voice"
    combined = AudioSegment.empty()

    pause_letter = AudioSegment.silent(duration=letter_pause_ms)
    pause_word = AudioSegment.silent(duration=word_pause_ms)

    try:
        # 1. 生成单词发音
        temp_file = os.path.join(session_dir, "temp_voice_1.mp3")
        word_audio = await generate_audio_segment(preview_word, temp_file)
        combined += word_audio + pause_word

        # 2. 如果需要包含字母拼写
        if include_spelling:
            for char in preview_word:
                if char.isalpha():
                    char_audio = await generate_audio_segment(char, os.path.join(session_dir, "temp_char.mp3"))
                    combined += char_audio + pause_letter

        # 3. 再次读单词
        temp_file2 = os.path.join(session_dir, "temp_voice_2.mp3")
        word_audio2 = await generate_audio_segment(preview_word, temp_file2)
        combined += word_audio2 + pause_word

        # 4. 如果需要添加中文翻译发音
        if include_chinese:
            chinese_meaning = "声音"
            cn_audio = await generate_audio_segment(chinese_meaning, os.path.join(session_dir, "temp_cn.mp3"), CHINESE_VOICE)
            combined += cn_audio + pause_word

        # 导出为 preview.mp3
        output_path = os.path.join(session_dir, "preview.mp3")
        combined.export(output_path, format="mp3")

        # 清理临时文件
        for f in os.listdir(session_dir):
            if f.startswith('temp_'):
                try:
                    os.remove(os.path.join(session_dir, f))
                except:
                    pass

        return output_path, session_id

    except Exception as e:
        print(f"预览生成失败: {e}")
        import traceback
        traceback.print_exc()
        return None, session_id


async def generate_word_audio(word_en, word_cn, letter_pause_ms, word_pause_ms, include_spelling, include_word_spelling, include_chinese, session_dir):
    """为单个单词生成音频"""
    temp_files_to_clean = []
    combined = AudioSegment.empty()

    pause_letter = AudioSegment.silent(duration=letter_pause_ms)
    pause_word = AudioSegment.silent(duration=word_pause_ms)

    try:
        print(f"开始处理单词: {word_en}, 中文: {word_cn}")

        # 1. 生成单词发音
        temp_file = os.path.join(session_dir, f"temp_{word_en}_1.mp3")
        temp_files_to_clean.append(temp_file)
        word_audio = await generate_audio_segment(word_en, temp_file)
        combined += word_audio + pause_word
        print(f"  ✓ 单词发音生成成功")

        # 2. 如果需要包含字母拼写
        if include_spelling and ' ' not in word_en:
            for char in word_en:
                if char.isalpha():
                    char_audio = await generate_audio_segment(char, os.path.join(session_dir, "temp_char.mp3"))
                    combined += char_audio + pause_letter
            print(f"  ✓ 字母拼写生成成功")

        # 2.5. 如果需要包含组词拼写（词组逐词拼写）
        if include_word_spelling and ' ' in word_en:
            words_in_phrase = word_en.split()
            for phrase_word in words_in_phrase:
                for char in phrase_word:
                    if char.isalpha():
                        char_audio = await generate_audio_segment(char, os.path.join(session_dir, "temp_phrase_char.mp3"))
                        combined += char_audio + pause_letter
                # 词间停顿
                combined += pause_word
            print(f"  ✓ 组词拼写生成成功")

        # 3. 再次读单词
        temp_file2 = os.path.join(session_dir, f"temp_{word_en}_2.mp3")
        temp_files_to_clean.append(temp_file2)
        word_audio2 = await generate_audio_segment(word_en, temp_file2)
        combined += word_audio2 + pause_word
        print(f"  ✓ 单词再次发音生成成功")

        # 4. 如果需要添加中文翻译发音
        if include_chinese and word_cn:
            for i, cn in enumerate(word_cn):
                try:
                    cn_audio = await generate_audio_segment(cn, os.path.join(session_dir, f"temp_cn_{i}.mp3"), CHINESE_VOICE)
                    combined += cn_audio + pause_word
                except Exception as e:
                    print(f"  ⚠ 中文音频生成失败 '{cn}': {e}, 跳过")
                    continue
            if word_cn:
                print(f"  ✓ 中文翻译发音生成成功 ({len(word_cn)} 个)")

        # 文件命名（不包含中文）
        file_name = f"{word_en}.mp3"

        output_path = os.path.join(session_dir, file_name)
        combined.export(output_path, format="mp3")
        print(f"  ✓ 音频导出成功: {file_name}")

        return file_name, output_path

    except Exception as e:
        print(f"✗ 单词 '{word_en}' 生成失败: {e}")
        import traceback
        traceback.print_exc()
        return None, None

    finally:
        # 无论成功失败，都清理本会话目录下所有 temp_ 开头的临时文件
        # （含 temp_char / temp_phrase_char / temp_cn_* 等，避免残留被打进下载压缩包）
        for f in os.listdir(session_dir):
            if f.startswith('temp_'):
                try:
                    os.remove(os.path.join(session_dir, f))
                except:
                    pass


async def process_words_async(word_entries, letter_pause_ms, word_pause_ms, include_spelling, include_word_spelling, include_chinese, include_chinese_definition, session_id):
    """异步处理所有单词"""
    session_dir = os.path.join(app.config['OUTPUT_DIR'], session_id)
    os.makedirs(session_dir, exist_ok=True)

    results = []
    total = len(word_entries)
    
    for i, entry in enumerate(word_entries):
        word = entry['word'].strip()
        if not word:
            continue

        # 更新进度
        generation_progress['current'] = i + 1
        generation_progress['total'] = total
        generation_progress['word'] = word

        # 获取中文翻译（多个）
        if include_chinese_definition:
            word_cn_list = [entry['chinese']] if entry.get('chinese') else []
        elif include_chinese:
            word_cn_list = get_youdao_translation(word)
        else:
            word_cn_list = []

        file_name, file_path = await generate_word_audio(
            word, word_cn_list, letter_pause_ms, word_pause_ms, include_spelling, include_word_spelling, include_chinese, session_dir
        )
        if file_name:
            results.append({"word": word, "filename": file_name, "chinese": ", ".join(word_cn_list)})

    # 标记完成
    generation_progress['completed'] = True

    # 清理所有临时文件
    for f in os.listdir(session_dir):
        if f.startswith('temp_'):
            try:
                os.remove(os.path.join(session_dir, f))
            except:
                pass

    return results, session_id


@app.route('/')
def index():
    """渲染主页面"""
    return render_template('index.html')


@app.route('/temp_files/<session_id>/<filename>')
def serve_preview(session_id, filename):
    """提供预览音频文件"""
    file_path = os.path.join(app.config['TEMP_DIR'], session_id, filename)
    if os.path.exists(file_path):
        return send_file(file_path, mimetype='audio/mpeg')
    return "File not found", 404


@app.route('/generated_audio/<session_id>/<filename>')
def serve_audio(session_id, filename):
    """提供生成的音频文件"""
    file_path = os.path.join(app.config['OUTPUT_DIR'], session_id, filename)
    if os.path.exists(file_path):
        return send_file(file_path, mimetype='audio/mpeg')
    return "File not found", 404


@app.route('/api/preview', methods=['POST'])
def preview():
    """生成预览音频"""
    data = request.json
    letter_pause = int(data.get('letterPause', 300))
    word_pause = int(data.get('wordPause', 2000))
    include_spelling = data.get('includeSpelling', True)
    include_word_spelling = data.get('includeWordSpelling', False)
    include_chinese = data.get('includeChinese', False)

    audio_path, session_id = asyncio.run(
        generate_preview_audio(letter_pause, word_pause, include_spelling, include_word_spelling, include_chinese)
    )

    if audio_path and os.path.exists(audio_path):
        return jsonify({
            "success": True,
            "sessionId": session_id,
            "audioUrl": f"/generated_audio/{session_id}/preview.mp3"
        })
    else:
        return jsonify({"success": False, "error": "预览生成失败"})


@app.route('/api/generate', methods=['POST'])
def generate():
    """批量生成音频"""
    if 'file' not in request.files:
        return jsonify({"success": False, "error": "请上传文件"})

    file = request.files['file']
    if file.filename == '':
        return jsonify({"success": False, "error": "请选择文件"})

    # 解析参数
    letter_pause = int(request.form.get('letterPause', 300))
    word_pause = int(request.form.get('wordPause', 2000))
    include_spelling = request.form.get('includeSpelling', 'true').lower() == 'true'
    include_word_spelling = request.form.get('includeWordSpelling', 'false').lower() == 'true'
    include_chinese = request.form.get('includeChinese', 'false').lower() == 'true'
    include_chinese_definition = request.form.get('includeChineseDefinition', 'false').lower() == 'true'

    # 读取并解析单词列表
    content = file.read().decode('utf-8').strip()
    words = []
    word_entries = []
    if include_chinese_definition:
        for line in content.splitlines():
            line = line.strip()
            if not line:
                continue
            parts = line.split(',')
            if len(parts) < 2:
                return jsonify({"success": False, "error": "导入中文释义时，每行格式应为：英文, 中文"})
            english = parts[0].strip()
            chinese = ','.join(parts[1:]).strip()
            if not english or not chinese:
                return jsonify({"success": False, "error": "导入中文释义时，每行格式应为：英文, 中文"})
            word_entries.append({"word": english, "chinese": chinese})
    else:
        if ',' in content:
            words = [w.strip() for w in content.split(',') if w.strip()]
        else:
            words = [w.strip() for w in content.splitlines() if w.strip()]

    if not include_chinese_definition:
        word_entries = [{"word": w, "chinese": ""} for w in words]

    # 限制数量
    if len(word_entries) > 100:
        return jsonify({"success": False, "error": "单词数量不能超过100个"})

    if len(word_entries) == 0:
        return jsonify({"success": False, "error": "文件中没有找到有效单词"})

    # 生成会话ID
    session_id = str(uuid.uuid4())

    # 初始化进度
    generation_progress['session_id'] = session_id
    generation_progress['current'] = 0
    generation_progress['total'] = len(word_entries)
    generation_progress['word'] = ''
    generation_progress['completed'] = False

    # 处理单词
    try:
        results, _ = asyncio.run(
            process_words_async(word_entries, letter_pause, word_pause, include_spelling, include_word_spelling, include_chinese, include_chinese_definition, session_id)
        )
        print(f"生成完成，结果数量: {len(results)}")
    except Exception as e:
        print(f"处理单词时出错: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "error": f"处理出错: {str(e)}"})

    if results:
        log_usage(len(results))
        return jsonify({
            "success": True,
            "sessionId": session_id,
            "count": len(results),
            "words": results
        })
    else:
        print("警告: 没有生成任何音频文件")
        return jsonify({"success": False, "error": "生成失败，未生成任何音频文件"})


@app.route('/api/progress', methods=['GET'])
def get_progress():
    """获取生成进度"""
    return jsonify({
        "current": generation_progress['current'],
        "total": generation_progress['total'],
        "word": generation_progress['word'],
        "completed": generation_progress['completed']
    })


@app.route('/api/download/<session_id>', methods=['GET'])
def download(session_id):
    """打包下载所有音频文件"""
    session_dir = os.path.join(app.config['OUTPUT_DIR'], session_id)

    if not os.path.exists(session_dir):
        return jsonify({"success": False, "error": "会话不存在或已过期"})

    # 创建 zip 文件
    zip_filename = f"LexiVoice_{session_id[:8]}.zip"
    zip_path = os.path.join(app.config['TEMP_DIR'], zip_filename)

    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for file in os.listdir(session_dir):
            # 排除临时文件（temp_*），只打包正式生成的单词音频
            if file.endswith('.mp3') and not file.startswith('temp_'):
                file_path = os.path.join(session_dir, file)
                zipf.write(file_path, file)

    return send_file(zip_path, as_attachment=True, download_name=zip_filename, mimetype='application/zip')


@app.route('/api/download-single/<session_id>/<filename>', methods=['GET'])
def download_single(session_id, filename):
    """下载单个音频文件"""
    file_path = os.path.join(app.config['OUTPUT_DIR'], session_id, filename)
    if os.path.exists(file_path):
        return send_file(file_path, as_attachment=True, mimetype='audio/mpeg')
    return jsonify({"success": False, "error": "文件不存在"})


@app.route('/cleanup', methods=['POST'])
def cleanup_session():
    """清理会话文件"""
    data = request.json
    session_id = data.get('sessionId')

    # 清理预览文件
    preview_dir = os.path.join(app.config['TEMP_DIR'], session_id)
    if os.path.exists(preview_dir):
        shutil.rmtree(preview_dir)

    # 清理生成的音频文件
    audio_dir = os.path.join(app.config['OUTPUT_DIR'], session_id)
    if os.path.exists(audio_dir):
        shutil.rmtree(audio_dir)

    return jsonify({"success": True})


@app.route('/api/cleanup-all', methods=['POST'])
def cleanup_all():
    """清理所有临时文件和过期会话"""
    import time
    
    # 清理 generated_audio 中的 temp_ 文件和过期会话（超过24小时）
    output_dir = app.config['OUTPUT_DIR']
    temp_dir = app.config['TEMP_DIR']
    current_time = time.time()
    max_age = 24 * 60 * 60  # 24小时
    cleaned_count = 0
    
    # 清理 generated_audio 目录
    for session_id in os.listdir(output_dir):
        session_path = os.path.join(output_dir, session_id)
        if not os.path.isdir(session_path):
            continue
        
        # 检查是否过期
        if current_time - os.path.getmtime(session_path) > max_age:
            try:
                shutil.rmtree(session_path)
                cleaned_count += 1
                print(f"已清理过期会话: {session_id}")
            except Exception as e:
                print(f"清理会话失败 {session_id}: {e}")
            continue
        
        # 清理临时文件
        for f in os.listdir(session_path):
            if f.startswith('temp_') or f.endswith('.zip'):
                try:
                    os.remove(os.path.join(session_path, f))
                    cleaned_count += 1
                except:
                    pass
    
    # 清理 temp_files 目录
    for session_id in os.listdir(temp_dir):
        session_path = os.path.join(temp_dir, session_id)
        if not os.path.isdir(session_path):
            continue
        
        if current_time - os.path.getmtime(session_path) > max_age:
            try:
                shutil.rmtree(session_path)
                cleaned_count += 1
            except Exception as e:
                print(f"清理临时文件失败 {session_id}: {e}")
    
    return jsonify({"success": True, "cleaned": cleaned_count})


def cleanup_old_files():
    """启动时清理过期文件"""
    import time
    output_dir = app.config['OUTPUT_DIR']
    temp_dir = app.config['TEMP_DIR']
    current_time = time.time()
    max_age = 24 * 60 * 60  # 24小时
    cleaned_count = 0
    
    for session_id in os.listdir(output_dir):
        session_path = os.path.join(output_dir, session_id)
        if not os.path.isdir(session_path):
            continue
        
        if current_time - os.path.getmtime(session_path) > max_age:
            try:
                shutil.rmtree(session_path)
                cleaned_count += 1
            except:
                pass
            continue
        
        for f in os.listdir(session_path):
            if f.startswith('temp_') or f.endswith('.zip'):
                try:
                    os.remove(os.path.join(session_path, f))
                    cleaned_count += 1
                except:
                    pass
    
    for session_id in os.listdir(temp_dir):
        session_path = os.path.join(temp_dir, session_id)
        if os.path.isdir(session_path) and current_time - os.path.getmtime(session_path) > max_age:
            try:
                shutil.rmtree(session_path)
                cleaned_count += 1
            except:
                pass
    
    if cleaned_count > 0:
        print(f"启动时已清理 {cleaned_count} 个过期文件")


if __name__ == '__main__':
    cleanup_old_files()
    app.run(debug=True, host='0.0.0.0', port=8080)
