# step3_generate_report.py
import json
import os
from datetime import datetime
from jinja2 import Template

# ============================================================================
# CONFIGURATION
# ============================================================================
INPUT_JSON_FILE = "analyzed_profiles_live.json"
OUTPUT_HTML_FILE = "matchmaking_live_report.html"
REPORT_TITLE = "Отчет по анализу совместимости | Matchmaking Engine LIVE"
REPORT_DATE = datetime.now().strftime("%d.%m.%Y %H:%M")

# ============================================================================
# HTML TEMPLATE (Jinja2)
# ============================================================================
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ report_title }}</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400&display=swap');

        :root {
            --bg-dark: #0a0a0f;
            --card-bg: #161b22;
            --border: #30363d;
            --text-primary: #e6edf3;
            --text-secondary: #8b949e;
            --accent-blue: #58a6ff;
            --accent-green: #3fb950;
            --accent-orange: #d29922;
            --accent-red: #f85149;
            --font-mono: 'JetBrains Mono', monospace;
        }

        * { margin: 0; padding: 0; box-sizing: border-box; }

        body {
            font-family: 'Inter', sans-serif;
            background-color: var(--bg-dark);
            color: var(--text-primary);
            line-height: 1.6;
            padding: 20px;
        }

        .container { max-width: 1000px; margin: 0 auto; }

        .header {
            text-align: center;
            margin-bottom: 40px;
            padding-bottom: 20px;
            border-bottom: 1px solid var(--border);
        }
        .header h1 { font-size: 2rem; font-weight: 700; margin-bottom: 5px; }
        .header .date { color: var(--text-secondary); font-size: 0.9rem; }

        .profile-card {
            background: var(--card-bg);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 25px;
            margin-bottom: 30px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.2);
            display: flex;
            flex-direction: row;
            gap: 20px;
        }

        .profile-photo {
            flex-shrink: 0;
            width: 150px;
            height: 150px;
            border-radius: 12px;
            overflow: hidden;
            border: 2px solid var(--border);
            background: #000;
        }
        .profile-photo img {
            width: 100%;
            height: 100%;
            object-fit: cover;
        }
        .profile-photo img.no-photo {
            opacity: 0.5;
            object-fit: contain;
            padding: 20px;
        }

        .card-content {
            flex: 1;
            display: flex;
            flex-direction: column;
        }

        .card-header {
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            margin-bottom: 20px;
            padding-bottom: 15px;
            border-bottom: 1px solid var(--border);
            flex-wrap: wrap;
            gap: 10px;
        }

        .user-info {
            flex: 1;
        }
        .user-info h2 {
            font-size: 1.5rem;
            color: var(--text-primary);
            display: flex;
            align-items: center;
            gap: 10px;
            flex-wrap: wrap;
        }
        .copy-url-btn {
            background: rgba(88, 166, 255, 0.2);
            border: 1px solid var(--accent-blue);
            color: var(--accent-blue);
            padding: 4px 10px;
            border-radius: 20px;
            font-size: 0.7rem;
            font-weight: normal;
            cursor: pointer;
            transition: all 0.2s;
            font-family: inherit;
        }
        .copy-url-btn:hover {
            background: var(--accent-blue);
            color: #0a0a0f;
        }
        .copy-url-btn.copied {
            background: var(--accent-green);
            border-color: var(--accent-green);
            color: #0a0a0f;
        }
        .user-meta { color: var(--text-secondary); font-size: 0.9rem; margin-top: 4px; }

        .score-badge {
            padding: 6px 12px;
            border-radius: 20px;
            font-weight: 600;
            font-size: 0.9rem;
            border: 1px solid transparent;
            white-space: nowrap;
        }
        .score-high { background: rgba(63, 185, 80, 0.15); color: var(--accent-green); border-color: var(--accent-green); }
        .score-med { background: rgba(210, 153, 34, 0.15); color: var(--accent-orange); border-color: var(--accent-orange); }
        .score-low { background: rgba(248, 81, 73, 0.15); color: var(--accent-red); border-color: var(--accent-red); }

        .traits-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
            gap: 15px;
            margin-bottom: 20px;
        }
        .trait-item {
            background: rgba(255,255,255,0.03);
            padding: 10px;
            border-radius: 8px;
        }
        .trait-label { display: flex; justify-content: space-between; font-size: 0.85rem; margin-bottom: 6px; }
        .progress-bar { height: 6px; background: #30363d; border-radius: 3px; overflow: hidden; }
        .progress-fill { height: 100%; border-radius: 3px; }

        .fill-ext { background: #58a6ff; }
        .fill-neu { background: #f85149; }
        .fill-con { background: #3fb950; }
        .fill-opn { background: #bc8cff; }
        .fill-agr { background: #d29922; }

        .section-title { font-size: 1.1rem; font-weight: 600; margin: 20px 0 10px 0; color: var(--text-primary); }
        .analysis-box {
            background: rgba(255,255,255,0.02);
            border-left: 3px solid var(--accent-blue);
            padding: 15px;
            border-radius: 0 8px 8px 0;
            font-size: 0.95rem;
            color: #c9d1d9;
        }
        .red-flags {
            border-left-color: var(--accent-red);
            background: rgba(248, 81, 73, 0.05);
        }
        .red-flags ul { list-style: none; padding-left: 0; }
        .red-flags li::before { content: "⚠️ "; }

        .message-container {
            margin-top: 15px;
            display: flex;
            align-items: flex-start;
            gap: 10px;
        }
        .message-preview {
            flex: 1;
            background: #0d1117;
            border: 1px solid var(--border);
            padding: 15px;
            border-radius: 8px;
            font-family: var(--font-mono);
            font-size: 0.9rem;
            color: #a5d6ff;
            white-space: pre-wrap;
        }
        .copy-btn {
            background: var(--accent-blue);
            border: none;
            color: #0a0a0f;
            font-weight: bold;
            padding: 8px 12px;
            border-radius: 6px;
            cursor: pointer;
            font-size: 0.8rem;
            transition: background 0.2s;
            white-space: nowrap;
            height: fit-content;
        }
        .copy-btn:hover {
            background: #7ab4ff;
        }
        .copy-btn.copied {
            background: var(--accent-green);
            color: white;
        }

        .mass-action-panel {
            margin-top: 60px;
            padding: 30px;
            background: #1f2428;
            border: 2px solid var(--accent-blue);
            border-radius: 12px;
        }
        .panel-header {
            font-size: 1.4rem;
            font-weight: 700;
            color: var(--accent-blue);
            margin-bottom: 20px;
            display: flex;
            align-items: center;
            gap: 10px;
        }
        .copy-section { margin-bottom: 25px; }
        .copy-label {
            display: block;
            font-weight: 600;
            margin-bottom: 8px;
            color: var(--text-secondary);
            font-size: 0.9rem;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        textarea {
            width: 100%;
            height: 150px;
            background: #0d1117;
            border: 1px solid var(--border);
            color: var(--text-primary);
            padding: 15px;
            font-family: var(--font-mono);
            font-size: 0.85rem;
            border-radius: 8px;
            resize: vertical;
        }
        textarea:focus { outline: 2px solid var(--accent-blue); border-color: transparent; }
        .hint { font-size: 0.8rem; color: var(--text-secondary); margin-top: 5px; }

        .footer { text-align: center; margin-top: 40px; color: var(--text-secondary); font-size: 0.8rem; }

        .toast {
            position: fixed;
            bottom: 20px;
            right: 20px;
            background: var(--accent-green);
            color: #0a0a0f;
            padding: 8px 16px;
            border-radius: 8px;
            font-size: 0.9rem;
            font-weight: bold;
            opacity: 0;
            transition: opacity 0.3s;
            pointer-events: none;
            z-index: 1000;
        }
        .toast.show {
            opacity: 1;
        }

        @media (max-width: 768px) {
            .profile-card { flex-direction: column; }
            .profile-photo { width: 100%; height: 200px; }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>{{ report_title }}</h1>
            <p class="date">Сгенерировано: {{ report_date }}</p>
        </div>

        {% for item in profiles %}
        <div class="profile-card">
            <!-- Photo Section -->
            <div class="profile-photo">
                {% if item.profile.photo_100 %}
                    <img src="{{ item.profile.photo_100 }}" alt="{{ item.profile.first_name }}">
                {% else %}
                    <img src="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='%238b949e'%3E%3Cpath d='M12 12c2.21 0 4-1.79 4-4s-1.79-4-4-4-4 1.79-4 4 1.79 4 4 4zm0 2c-2.67 0-8 1.34-8 4v2h16v-2c0-2.66-5.33-4-8-4z'/%3E%3C/svg%3E" class="no-photo" alt="No Photo">
                {% endif %}
            </div>

            <div class="card-content">
                <div class="card-header">
                    <div class="user-info">
                        <h2>
                            {{ item.profile.first_name }} {{ item.profile.last_name }}
                            <button class="copy-url-btn" data-url="https://vk.com/id{{ item.profile.id }}">🔗 Copy URL</button>
                        </h2>
                        <div class="user-meta">
                            📍 {{ item.profile.city.title if item.profile.city else 'N/A' }} &nbsp;|&nbsp;
                            🎂 {{ item.profile.bdate }} &nbsp;|&nbsp;
                            ID: {{ item.profile.id }}
                        </div>
                        {% if item.profile.status %}
                        <div class="user-meta" style="margin-top:5px; font-style:italic;">"{{ item.profile.status }}"</div>
                        {% endif %}
                    </div>
                    <div class="score-badge {% if item.analysis.compatibility_score >= 80 %}score-high{% elif item.analysis.compatibility_score >= 60 %}score-med{% else %}score-low{% endif %}">
                        {{ item.analysis.compatibility_score }}% Match
                    </div>
                </div>

                <div class="traits-grid">
                    {% set traits = [
                        ('extraversion', 'Экстраверсия', 'fill-ext'),
                        ('neuroticism', 'Нейротизм', 'fill-neu'),
                        ('conscientiousness', 'Добросовестность', 'fill-con'),
                        ('openness', 'Открытость', 'fill-opn'),
                        ('agreeableness', 'Доброжелательность', 'fill-agr')
                    ] %}
                    {% for key, label, css_class in traits %}
                    <div class="trait-item">
                        <div class="trait-label">
                            <span>{{ label }}</span>
                            <span>{{ item.analysis.big_five[key] }}%</span>
                        </div>
                        <div class="progress-bar">
                            <div class="progress-fill {{ css_class }}" style="width: {{ item.analysis.big_five[key] }}%"></div>
                        </div>
                    </div>
                    {% endfor %}
                </div>

                <div class="section-title">🧠 Личностный портрет</div>
                <div class="analysis-box">{{ item.analysis.personality_summary }}</div>

                {% if item.analysis.red_flags %}
                <div class="section-title">🚩 Зоны риска</div>
                <div class="analysis-box red-flags">
                    <ul>
                        {% for flag in item.analysis.red_flags %}
                        <li>{{ flag }}</li>
                        {% endfor %}
                    </ul>
                </div>
                {% endif %}

                <div class="section-title">💬 Вердикт</div>
                <div class="analysis-box">{{ item.analysis.verdict }}</div>

                <div class="section-title">✉️ Черновик сообщения</div>
                <div class="message-container">
                    <div class="message-preview" id="msg-{{ loop.index0 }}">{{ item.generated_message }}</div>
                    <button class="copy-btn" data-msg-id="msg-{{ loop.index0 }}">📋 Копировать</button>
                </div>
            </div>
        </div>
        {% endfor %}

        <div class="mass-action-panel">
            <div class="panel-header">
                ⚡ Панель массовых действий (Copy-Paste Ready)
            </div>

            <div class="copy-section">
                <label class="copy-label">1. Список URL профилей (для массового открытия вкладок)</label>
                <textarea id="url-list" readonly onclick="this.select()">{% for item in profiles %}https://vk.com/id{{ item.profile.id }}
{% endfor %}</textarea>
                <div class="hint">Нажмите на поле, чтобы выделить всё, затем Ctrl+C.</div>
            </div>

            <div class="copy-section">
                <label class="copy-label">2. Персональные приветствия (по одному на строку)</label>
                <textarea id="greeting-list" readonly onclick="this.select()">{% for item in profiles %}{{ item.generated_message }}
{% endfor %}</textarea>
                <div class="hint">Скопируйте этот список и вставьте в инструмент массовой рассылки.</div>
            </div>
        </div>

        <div class="footer">
            Generated by Matchmaking Engine v3.0 | Internal Use Only
        </div>
    </div>

    <div id="toast" class="toast">✅ Скопировано!</div>

    <script>
        function showToast() {
            const toast = document.getElementById('toast');
            toast.classList.add('show');
            setTimeout(() => toast.classList.remove('show'), 1500);
        }

        document.querySelectorAll('.copy-url-btn').forEach(btn => {
            btn.addEventListener('click', function(e) {
                e.stopPropagation();
                const url = this.getAttribute('data-url');
                navigator.clipboard.writeText(url).then(() => {
                    const originalText = this.innerHTML;
                    this.innerHTML = '✅ Copied!';
                    this.classList.add('copied');
                    setTimeout(() => {
                        this.innerHTML = originalText;
                        this.classList.remove('copied');
                    }, 1500);
                    showToast();
                }).catch(err => {
                    console.error('Copy failed:', err);
                });
            });
        });

        document.querySelectorAll('.copy-btn').forEach(btn => {
            btn.addEventListener('click', function() {
                const msgId = this.getAttribute('data-msg-id');
                const msgDiv = document.getElementById(msgId);
                if (msgDiv) {
                    const text = msgDiv.innerText;
                    navigator.clipboard.writeText(text).then(() => {
                        const originalText = this.innerHTML;
                        this.innerHTML = '✅ Скопировано!';
                        this.classList.add('copied');
                        setTimeout(() => {
                            this.innerHTML = originalText;
                            this.classList.remove('copied');
                        }, 1500);
                        showToast();
                    }).catch(err => {
                        console.error('Copy failed:', err);
                    });
                }
            });
        });
    </script>
</body>
</html>
"""

# ============================================================================
# DATA SANITIZATION & SORTING
# ============================================================================
def sanitize_profile(profile):
    if 'analysis' not in profile:
        profile['analysis'] = {}
    analysis = profile['analysis']

    analysis.setdefault('compatibility_score', 0)
    analysis.setdefault('verdict', 'Нет данных')
    analysis.setdefault('red_flags', [])
    analysis.setdefault('personality_summary', 'Нет описания')

    if 'big_five' not in analysis:
        analysis['big_five'] = {}
    bf = analysis['big_five']
    defaults = {
        'extraversion': 50,
        'neuroticism': 50,
        'conscientiousness': 50,
        'openness': 50,
        'agreeableness': 50
    }
    for key, default_val in defaults.items():
        bf.setdefault(key, default_val)

    profile.setdefault('generated_message', 'Сообщение не сгенерировано')
    return profile

def load_and_sort_data(filepath):
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"❌ Critical Error: File '{filepath}' not found.")

    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)

        if isinstance(data, list):
            profiles = data
        elif isinstance(data, dict) and 'profiles' in data:
            profiles = data['profiles']
        else:
            raise ValueError("JSON format unsupported.")

        profiles = [sanitize_profile(p) for p in profiles]
        profiles.sort(key=lambda x: x['analysis'].get('compatibility_score', 0), reverse=True)
        return profiles

    except json.JSONDecodeError:
        raise ValueError(f"❌ Invalid JSON in {filepath}")

def generate_report(data, output_file):
    template = Template(HTML_TEMPLATE)
    html_content = template.render(
        report_title=REPORT_TITLE,
        report_date=REPORT_DATE,
        profiles=data
    )
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html_content)

    print(f"✅ SUCCESS: Report generated -> {output_file}")
    print(f"📊 Profiles processed (sorted by score): {len(data)}")

if __name__ == "__main__":
    try:
        profiles_data = load_and_sort_data(INPUT_JSON_FILE)
        generate_report(profiles_data, OUTPUT_HTML_FILE)
    except Exception as e:
        print(f"\n🔥 ERROR: {e}\n")
        exit(1)
