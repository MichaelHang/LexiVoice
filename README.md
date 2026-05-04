# 🎙️ LexiVoice: 单词音频生成器 Web 版

**LexiVoice** 是一个功能强大的在线工具，专为英语学习者设计。它可以导入包含英文单词列表的 txt 文件，自动获取有道词典翻译，并使用 Microsoft Edge Neural TTS 生成高质量的字母拼读练习音频。

## 🎧 音频结构

每个生成的 MP3 都遵循优化的记忆节奏模式：
1. **单词发音** (自然神经网络语音)
2. *可配置的停顿间隔*
3. **逐字母拼读** (字母间可配置停顿)
4. **单词发音** (重复)
5. *可配置的停顿间隔*

---

## ✨ 主要功能

- **文件导入**: 支持 txt 文件导入，批量生成时最多 20 个单词
- **导入中文释义**: 支持 `英文, 中文` 每行格式导入，自定义中文释义后直接生成中文朗读
- **预览功能**: 使用 "Voice" 作为示例单词，可实时调整参数后预览效果
- **拼写读音**: 可选择是否包含字母拼写读音
- **间隔配置**: 可自由调整字母停顿间隔和单词停顿间隔
- **中文翻译**: 可选择自动获取有道词典翻译并添加中文发音
- **打包下载**: 一键下载所有生成的音频文件

---

## 🛠️ 本地运行

### 1. 环境要求

- **Python 3.7+**
- **FFmpeg**: 音频处理必需
  - **macOS**: `brew install ffmpeg`
  - **Ubuntu**: `sudo apt install ffmpeg`
  - **Windows**: 从 [Gyan.dev](https://www.gyan.dev/ffmpeg/builds/) 下载并添加到系统 Path

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

### 3. 启动服务

```bash
# 直接启动
python app.py

# 或使用启动脚本 (macOS/Linux)
chmod +x start.sh
./start.sh
```

访问 http://localhost:5000

---

## 🚀 服务器部署

### Docker 部署 (推荐)

```bash
# 构建并启动
docker-compose up -d

# 查看日志
docker-compose logs -f
```

### Gunicorn + Nginx 部署

```bash
# 安装依赖
pip install -r requirements.txt

# 使用 gunicorn 运行
gunicorn -w 2 -b 0.0.0.0:5000 --timeout 300 app:app

# 配置 Nginx 反向代理
```

### PM2 部署

```bash
npm install -g pm2
pm2 start app.py --name lexicovoice --interpreter python3
pm2 save
pm2 startup
```

---

## 📁 项目结构

```
LexiVoice/
├── app.py              # Flask 后端 API
├── templates/
│   └── index.html      # 前端页面
├── static/
│   ├── css/
│   │   └── style.css   # 样式文件
│   └── js/
│       └── app.js      # 前端脚本
├── requirements.txt    # Python 依赖
├── Dockerfile          # Docker 镜像配置
├── docker-compose.yml  # Docker Compose 配置
├── start.sh           # 启动脚本
└── README.md          # 本文档
```

---

## 🔧 配置说明

| 参数 | 默认值 | 说明 |
|------|--------|------|
| 字母停顿 | 300ms | 字母之间的停顿时长 |
| 单词停顿 | 2000ms | 单词之间的停顿时长 |
| 包含拼写 | 是 | 是否包含字母拼读 |
| 中文翻译 | 否 | 是否添加中文朗读 |

---

## 📝 单词文件格式

支持两种导入方式：

**每行一个:**
```
hello
world
voice
apple
banana
```

**英文, 中文**
```
hello, 你好
world, 世界
voice, 声音
apple, 苹果
banana, 香蕉
```

启用“导入中文释义”选项后，系统会使用每行提供的中文文本直接生成中文朗读。
---

## 🌐 技术栈

- **后端**: Flask + edge-tts + pydub
- **前端**: 原生 HTML/CSS/JavaScript
- **TTS**: Microsoft Edge Neural TTS
- **翻译**: 有道词典 API

---

## ⚠️ 注意事项

1. 生成的音频文件存储在 `generated_audio/` 目录
2. 临时文件存储在 `temp_files/` 目录
3. 音频文件会在会话结束后自动清理
4. 确保网络连接正常，以便获取翻译和生成 TTS

## 📜 许可证

MIT License