/**
 * LexiVoice Web UI JavaScript
 */

let currentSessionId = null;
let selectedFile = null;
let previewAudio = null;
let isGenerating = false;
let previewGenerated = false;
let previewAudioUrl = null;

// DOM Elements
const uploadArea = document.getElementById('uploadArea');
const fileInput = document.getElementById('fileInput');
const fileInfo = document.getElementById('fileInfo');
const fileName = document.getElementById('fileName');
const wordCount = document.getElementById('wordCount');
const wordListPreview = document.getElementById('wordListPreview');
const wordTags = document.getElementById('wordTags');
const generateBtn = document.getElementById('generateBtn');
const previewBtn = document.getElementById('previewBtn');
const stopPreviewBtn = document.getElementById('stopPreviewBtn');
const resultsSection = document.getElementById('resultsSection');
const resultsCount = document.getElementById('resultsCount');
const resultsList = document.getElementById('resultsList');
const downloadAllBtn = document.getElementById('downloadAllBtn');
const previewStatusBar = document.getElementById('previewStatus');
const generateStatusBar = document.getElementById('generateStatus');

// Settings Elements
const includeSpelling = document.getElementById('includeSpelling');
const includeWordSpelling = document.getElementById('includeWordSpelling');
const includeChineseDefinition = document.getElementById('includeChineseDefinition');
const includeChinese = document.getElementById('includeChinese');
const letterPause = document.getElementById('letterPause');
const letterPauseRange = document.getElementById('letterPauseRange');
const wordPause = document.getElementById('wordPause');
const wordPauseRange = document.getElementById('wordPauseRange');

// 重置预览状态
function resetPreviewState() {
    previewGenerated = false;
    previewAudioUrl = null;
    if (previewAudio) {
        previewAudio.pause();
        previewAudio = null;
    }
    previewBtn.innerHTML = '<span class="btn-icon">🎵</span>生成预览';
    previewBtn.disabled = false;
    stopPreviewBtn.style.display = 'none';
    setPreviewStatus('');
}

// Sync range and number inputs
letterPauseRange.addEventListener('input', () => {
    letterPause.value = letterPauseRange.value;
    if (previewGenerated) resetPreviewState();
});

letterPause.addEventListener('change', () => {
    letterPauseRange.value = letterPause.value;
    if (previewGenerated) resetPreviewState();
});

wordPauseRange.addEventListener('input', () => {
    wordPause.value = wordPauseRange.value;
    if (previewGenerated) resetPreviewState();
});

wordPause.addEventListener('change', () => {
    wordPauseRange.value = wordPause.value;
    if (previewGenerated) resetPreviewState();
});

// 勾选框变化时重置预览
includeSpelling.addEventListener('change', () => {
    updateWordSpellingState();
    if (previewGenerated) resetPreviewState();
});

includeWordSpelling.addEventListener('change', () => {
    if (previewGenerated) resetPreviewState();
});

includeChineseDefinition.addEventListener('change', () => {
    if (selectedFile) {
        handleFile(selectedFile);
    }
});

includeChinese.addEventListener('change', () => {
    if (previewGenerated) resetPreviewState();
});

// 更新组词拼写状态
function updateWordSpellingState() {
    if (includeSpelling.checked) {
        includeWordSpelling.disabled = false;
    } else {
        includeWordSpelling.disabled = true;
        includeWordSpelling.checked = false;
    }
}

// File Upload Handling
uploadArea.addEventListener('click', () => fileInput.click());

uploadArea.addEventListener('dragover', (e) => {
    e.preventDefault();
    uploadArea.classList.add('dragover');
});

uploadArea.addEventListener('dragleave', () => {
    uploadArea.classList.remove('dragover');
});

uploadArea.addEventListener('drop', (e) => {
    e.preventDefault();
    uploadArea.classList.remove('dragover');
    const files = e.dataTransfer.files;
    if (files.length > 0 && files[0].type === 'text/plain') {
        handleFile(files[0]);
    }
});

fileInput.addEventListener('change', () => {
    if (fileInput.files.length > 0) {
        handleFile(fileInput.files[0]);
    }
});

function handleFile(file) {
    selectedFile = file;
    fileName.textContent = file.name;
    fileInfo.style.display = 'flex';

    // 隐藏之前的生成结果
    resultsSection.style.display = 'none';
    currentSessionId = null;

    const reader = new FileReader();
    reader.onload = (e) => {
        const content = e.target.result;
        let parsed;

        if (includeChineseDefinition.checked) {
            parsed = parseWordPairs(content);
            if (parsed.error) {
                showToast(parsed.error, 'error');
                selectedFile = null;
                fileInfo.style.display = 'none';
                return;
            }
        } else {
            parsed = { items: parseWords(content), error: '' };
        }

        wordCount.textContent = `共 ${parsed.items.length} 个单词`;

        if (parsed.items.length > 100) {
            showToast('单词数量不能超过100个', 'error');
            selectedFile = null;
            fileInfo.style.display = 'none';
            return;
        }

        if (parsed.items.length > 0) {
            wordTags.innerHTML = parsed.items.slice(0, 50).map(item => {
                if (includeChineseDefinition.checked) {
                    return `<span class="word-tag">${item.word}：${item.chinese}</span>`;
                }
                return `<span class="word-tag">${item}</span>`;
            }).join('') + (parsed.items.length > 50 ? '<span class="word-tag">...</span>' : '');

            if (parsed.items.length > 50) {
                wordTags.innerHTML += `<span class="word-tag">还有 ${parsed.items.length - 50} 个</span>`;
            }

            wordListPreview.style.display = 'block';
            generateBtn.disabled = false;
        }
    };
    reader.readAsText(file);
}

function parseWordPairs(content) {
    const lines = content.split(/\r?\n/);
    const items = [];

    for (let rawLine of lines) {
        const line = rawLine.trim();
        if (!line) continue;
        const parts = line.split(',');
        if (parts.length < 2) {
            return { items: [], error: '导入中文释义时，每行格式应为：英文, 中文' };
        }

        const word = parts[0].trim();
        const chinese = parts.slice(1).join(',').trim();
        if (!word || !chinese) {
            return { items: [], error: '导入中文释义时，每行格式应为：英文, 中文' };
        }

        items.push({ word, chinese });
    }

    return { items, error: '' };
}

function parseWords(content) {
    let words = [];
    if (content.includes(',')) {
        words = content.split(',').map(w => w.trim()).filter(w => w);
    } else {
        words = content.split('\n').map(w => w.trim()).filter(w => w);
    }
    return words;
}

// 生成预览
async function generatePreview() {
    previewBtn.disabled = true;
    previewBtn.innerHTML = '<span class="btn-icon">⏳</span>生成中...';
    setPreviewStatus('正在生成预览音频...', 'loading');

    try {
        const response = await fetch('/api/preview', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                letterPause: parseInt(letterPause.value),
                wordPause: parseInt(wordPause.value),
                includeSpelling: includeSpelling.checked,
                includeWordSpelling: includeWordSpelling.checked,
                includeChinese: includeChinese.checked
            })
        });

        const data = await response.json();

        if (data.success) {
            currentSessionId = data.sessionId;
            previewAudioUrl = data.audioUrl + '?t=' + new Date().getTime();
            previewGenerated = true;
            
            // 生成完成后显示播放按钮
            previewBtn.innerHTML = '<span class="btn-icon">▶</span>播放';
            previewBtn.disabled = false;
            stopPreviewBtn.style.display = 'inline-flex';
            
            setPreviewStatus('预览已生成，点击播放', 'success');
        } else {
            showToast(data.error || '预览生成失败', 'error');
            setPreviewStatus(data.error || '预览生成失败', 'error');
            previewBtn.innerHTML = '<span class="btn-icon">🎵</span>生成预览';
            previewBtn.disabled = false;
        }
    } catch (error) {
        console.error('请求错误:', error);
        showToast('网络错误', 'error');
        setPreviewStatus('网络错误', 'error');
        previewBtn.innerHTML = '<span class="btn-icon">🎵</span>生成预览';
        previewBtn.disabled = false;
    }
}

// 播放预览
async function playPreview() {
    if (!previewGenerated || !previewAudioUrl) return;
    
    if (previewAudio) {
        previewAudio.pause();
        previewAudio = null;
    }
    
    previewAudio = new Audio(previewAudioUrl);
    previewAudio.volume = 1.0;
    
    previewAudio.onplay = () => {
        setPreviewStatus('正在播放预览: Voice', 'success');
        previewBtn.innerHTML = '<span class="btn-icon">⏸</span>暂停';
        previewBtn.disabled = false;
    };

    previewAudio.onended = () => {
        previewBtn.innerHTML = '<span class="btn-icon">▶</span>播放';
        previewBtn.disabled = false;
        setPreviewStatus('预览播放完成', 'success');
        previewAudio = null;
    };

    previewAudio.onerror = () => {
        showToast('音频加载失败', 'error');
        setPreviewStatus('音频加载失败', 'error');
        previewBtn.innerHTML = '<span class="btn-icon">▶</span>播放';
        previewBtn.disabled = false;
        previewAudio = null;
    };
    
    try {
        await previewAudio.play();
    } catch (e) {
        showToast('请先点击页面再播放', 'error');
        previewBtn.innerHTML = '<span class="btn-icon">▶</span>播放';
        previewBtn.disabled = false;
    }
}

// 停止预览
function stopPreview() {
    if (previewAudio) {
        previewAudio.pause();
        previewAudio = null;
    }
    previewBtn.innerHTML = '<span class="btn-icon">▶</span>播放';
    previewBtn.disabled = false;
    setPreviewStatus('已停止', '');
}

// 预览按钮点击
previewBtn.addEventListener('click', () => {
    if (!previewGenerated) {
        // 未生成，先生成
        generatePreview();
    } else if (previewAudio && !previewAudio.paused) {
        // 正在播放，暂停
        previewAudio.pause();
    } else {
        // 已生成，播放
        playPreview();
    }
});

stopPreviewBtn.addEventListener('click', () => {
    stopPreview();
});

// Generate Audio
generateBtn.addEventListener('click', async () => {
    if (!selectedFile || isGenerating) return;

    // 清理上次的会话
    if (currentSessionId) {
        try {
            await fetch('/cleanup', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ sessionId: currentSessionId })
            });
        } catch (e) {}
    }

    isGenerating = true;
    generateBtn.disabled = true;
    generateBtn.innerHTML = '<span class="btn-icon">⏳</span>生成中...';
    
    // 显示进度条
    const progressContainer = document.getElementById('progressContainer');
    const progressFill = document.getElementById('progressFill');
    const progressText = document.getElementById('progressText');
    progressContainer.style.display = 'block';
    progressFill.style.width = '0%';
    progressText.textContent = '准备中...';

    // 轮询进度
    let progressInterval = setInterval(async () => {
        try {
            const res = await fetch('/api/progress');
            const prog = await res.json();
            
            if (prog.total > 0) {
                const percent = Math.round((prog.current / prog.total) * 100);
                progressFill.style.width = percent + '%';
                progressText.textContent = `处理中: ${prog.word} (${prog.current}/${prog.total})`;
            }
            
            if (prog.completed) {
                clearInterval(progressInterval);
            }
        } catch (e) {}
    }, 500);

    try {
        const formData = new FormData();
        formData.append('file', selectedFile);
        formData.append('letterPause', letterPause.value);
        formData.append('wordPause', wordPause.value);
        formData.append('includeSpelling', includeSpelling.checked.toString());
        formData.append('includeWordSpelling', includeWordSpelling.checked.toString());
        formData.append('includeChineseDefinition', includeChineseDefinition.checked.toString());
        formData.append('includeChinese', includeChinese.checked.toString());

        setGenerateStatus('正在处理单词并生成音频...', 'loading');

        console.log('正在上传文件:', selectedFile.name);

        const response = await fetch('/api/generate', {
            method: 'POST',
            body: formData
        });

        console.log('响应状态:', response.status);

        const data = await response.json();
        console.log('响应数据:', data);

        clearInterval(progressInterval);
        progressFill.style.width = '100%';

        if (data.success) {
            currentSessionId = data.sessionId;
            resultsCount.textContent = `成功生成 ${data.count} 个音频文件`;
            resultsList.innerHTML = '';
            resultsSection.style.display = 'block';
            showToast(`成功生成 ${data.count} 个音频文件`, 'success');
            setGenerateStatus('生成完成，点击下方按钮下载', 'success');
            progressText.textContent = '生成完成!';

            resultsSection.scrollIntoView({ behavior: 'smooth' });

        } else {
            console.error('生成失败:', data.error);
            showToast(data.error || '生成失败', 'error');
            setGenerateStatus(data.error || '生成失败', 'error');
            progressText.textContent = '生成失败';
        }
    } catch (error) {
        clearInterval(progressInterval);
        console.error('请求错误:', error);
        showToast('网络错误: ' + error.message, 'error');
        setGenerateStatus('网络错误: ' + error.message, 'error');
        progressText.textContent = '网络错误';
    }

    isGenerating = false;
    generateBtn.disabled = false;
    generateBtn.innerHTML = '<span class="btn-icon">🎵</span>开始生成音频';
    
    // 3秒后隐藏进度条
    setTimeout(() => {
        progressContainer.style.display = 'none';
    }, 3000);
});

// Play single audio
function playAudio(filename) {
    if (!currentSessionId) return;
    const audio = new Audio(`/generated_audio/${currentSessionId}/${filename}?t=${new Date().getTime()}`);
    audio.play().catch(err => showToast('播放失败', 'error'));
}

// Download single file
function downloadSingle(filename) {
    if (!currentSessionId) return;
    window.open(`/api/download-single/${currentSessionId}/${filename}`, '_blank');
}

// Download all as zip
downloadAllBtn.addEventListener('click', () => {
    if (!currentSessionId) return;
    window.open(`/api/download/${currentSessionId}`, '_blank');
});

// Preview Status helper
function setPreviewStatus(message, type) {
    previewStatusBar.textContent = message;
    previewStatusBar.className = 'status-bar ' + type;
}

// Generate Status helper
function setGenerateStatus(message, type) {
    generateStatusBar.textContent = message;
    generateStatusBar.className = 'status-bar ' + type;
}

// Toast notification
function showToast(message, type = '') {
    const toast = document.getElementById('toast');
    toast.textContent = message;
    toast.className = 'toast ' + type + ' show';
    setTimeout(() => {
        toast.className = 'toast';
    }, 3000);
}

// 初始化设置状态
document.addEventListener('DOMContentLoaded', () => {
    updateWordSpellingState();
});
