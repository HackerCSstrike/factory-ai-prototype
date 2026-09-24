import gradio as gr
import html
import os
import shutil
import time
from main import build_index, query_system

# Принудительно светлая тема
force_light_js = """
function() {
    document.body.classList.remove('dark');
    const observer = new MutationObserver(() => {
        if (document.body.classList.contains('dark')) document.body.classList.remove('dark');
    });
    observer.observe(document.body, { attributes: true, attributeFilter: ['class'] });
}
"""

# Идеально ровный, симметричный дизайн в цветах Gamma-презентации
CUSTOM_CSS = """
:root {
  --bg: #FAFAFA;            /* Светло-серый фон страницы */
  --surface: #FFFFFF;       /* Белые карточки */
  --primary: #D32F2F;       /* Малиново-красный акцент */
  --primary-hover: #B71C1C; /* Темно-красный при наведении */
  --secondary: #FADCD9;     /* Нежно-розовый фон */
  --text-main: #212121;     /* Темно-серый текст */
  --text-muted: #757575;    /* Приглушенный текст */
  --border: #E0E0E0;        /* Светло-серые границы */
  --radius: 4px;            /* Строгие, слегка скругленные углы */
}

footer { display: none !important; }
html, body, gradio-app { background: var(--bg) !important; color: var(--text-main) !important; font-family: 'Segoe UI', Roboto, Helvetica, Arial, sans-serif !important; }
.gradio-container { max-width: 900px !important; margin: 0 auto !important; padding: 40px 20px !important; }

/* Шапка - Строгая и по центру */
.header-container { text-align: center !important; margin-bottom: 40px !important; border-bottom: 3px solid var(--primary) !important; padding-bottom: 20px !important; }
.header-container h1 { font-size: 2.2rem !important; font-weight: 800 !important; color: var(--text-main) !important; margin: 0 !important; letter-spacing: -0.5px; }
.status-text { color: var(--text-muted) !important; font-size: 0.95rem !important; margin-top: 10px !important; font-weight: 500; }

/* Строка поиска - Идеально ровная */
.search-row { gap: 0 !important; flex-wrap: nowrap !important; align-items: stretch !important; box-shadow: 0 4px 12px rgba(0,0,0,0.05) !important; border-radius: var(--radius) !important; margin-bottom: 20px !important; }
.search-box { flex: 1 1 auto !important; min-width: 0 !important; background: transparent !important; border: none !important; box-shadow: none !important; padding: 0 !important; }
.search-box textarea {
  min-height: 60px !important; padding: 18px 24px !important; font-size: 1.1rem !important; line-height: 1.5 !important;
  background: var(--surface) !important; color: var(--text-main) !important; resize: none !important;
  border: 1px solid var(--border) !important; border-right: none !important; border-radius: var(--radius) 0 0 var(--radius) !important; box-shadow: none !important;
}
.search-box textarea:focus { border-color: var(--primary) !important; box-shadow: inset 0 0 0 1px var(--primary) !important; outline: none !important; }
.go-btn {
  flex: 0 0 160px !important; min-width: 160px !important; min-height: 60px !important;
  font-size: 1.1rem !important; font-weight: 700 !important; letter-spacing: 0.5px;
  background: var(--primary) !important; color: #fff !important; border: 1px solid var(--primary) !important;
  border-radius: 0 var(--radius) var(--radius) 0 !important; box-shadow: none !important; transition: background 0.2s;
}
.go-btn:hover { background: var(--primary-hover) !important; border-color: var(--primary-hover) !important; }

/* Режимы (Радио-кнопки) - По центру */
.modes { background: transparent !important; border: none !important; box-shadow: none !important; margin-bottom: 24px !important; }
.modes .wrap { justify-content: center !important; gap: 12px !important; }
.modes label {
  background: var(--surface) !important; border: 1px solid var(--border) !important; border-radius: 40px !important;
  padding: 10px 24px !important; font-size: 0.95rem !important; color: var(--text-muted) !important; cursor: pointer; transition: all 0.2s;
}
.modes label.selected { background: var(--secondary) !important; border-color: var(--primary) !important; color: var(--primary) !important; font-weight: 700 !important; }

/* Быстрые вопросы - По центру */
.suggested { justify-content: center !important; gap: 12px !important; margin-bottom: 40px !important; flex-wrap: wrap !important; }
.suggested button {
  background: var(--surface) !important; color: var(--text-main) !important; border: 1px solid var(--border) !important;
  border-radius: 40px !important; padding: 8px 20px !important; font-size: 0.9rem !important; box-shadow: none !important; transition: all 0.2s;
}
.suggested button:hover { background: var(--secondary) !important; color: var(--primary) !important; border-color: var(--secondary) !important; }

/* Блок файлов (Розовый акцент как на слайдах) */
.file-section { background: var(--secondary) !important; border: 1px solid #F4C4C4 !important; border-radius: var(--radius) !important; padding: 24px !important; margin-bottom: 40px !important; text-align: center !important; }
.file-section .prose { color: var(--primary) !important; font-weight: 700 !important; margin-bottom: 12px !important; font-size: 1.1rem !important; }
.file-section .hint { color: var(--text-main) !important; font-weight: 400 !important; font-size: 0.9rem !important; }
.reindex-btn { margin-top: 12px !important; background: var(--surface) !important; color: var(--text-main) !important; border: 1px solid var(--border) !important; border-radius: 40px !important; padding: 8px 20px !important; font-size: 0.9rem !important; cursor: pointer; transition: all 0.2s; display: inline-block !important; }
.reindex-btn:hover { background: var(--primary) !important; color: #fff !important; border-color: var(--primary) !important; }

/* Карточка ответа - Строгая с красной линией сверху */
.answer-card { background: var(--surface) !important; border: 1px solid var(--border) !important; border-top: 4px solid var(--primary) !important; border-radius: var(--radius) !important; padding: 32px !important; font-size: 1.1rem !important; line-height: 1.7 !important; color: var(--text-main) !important; box-shadow: 0 4px 20px rgba(0,0,0,0.03) !important; margin-bottom: 24px !important; }
.answer-card p { margin-bottom: 1em !important; }

/* Источники - Розовые плашки */
.quiet { border: 1px solid var(--border) !important; border-radius: var(--radius) !important; background: var(--surface) !important; overflow: hidden !important; }
.quiet .label-wrap { padding: 16px 20px !important; background: var(--bg) !important; }
.quiet .label-wrap span { font-weight: 700 !important; color: var(--text-main) !important; font-size: 1rem !important; }
.src { padding: 16px 20px !important; background: var(--secondary) !important; border-left: 4px solid var(--primary) !important; margin: 12px !important; border-radius: 0 var(--radius) var(--radius) 0 !important; }
.src-title { font-weight: 700 !important; color: var(--primary) !important; }
.src-page { color: var(--text-main) !important; font-weight: 600 !important; margin-left: 12px !important; }
.src-snippet { color: var(--text-main) !important; font-size: 0.95rem !important; margin-top: 8px !important; white-space: pre-wrap !important; line-height: 1.5 !important; }
"""

DOCS_DIR = "/app/data/docs"
EMPTY_ANSWER = '<span style="color: #757575; font-size: 1rem; text-align: center; display: block;">Введите вопрос в поле поиска выше. Ответ и источники появятся здесь.</span>'

SYSTEM_FONT = ("Segoe UI", "Roboto", "Helvetica Neue", "Arial", "sans-serif")
SYSTEM_MONO = ("Consolas", "Menlo", "Courier New", "monospace")

def get_server_files():
    os.makedirs(DOCS_DIR, exist_ok=True)
    return sorted([os.path.join(DOCS_DIR, f) for f in os.listdir(DOCS_DIR) if os.path.isfile(os.path.join(DOCS_DIR, f))])

def sync_files(uploaded_files):
    current_ui_files = uploaded_files if uploaded_files is not None else []
    ui_filenames = {os.path.basename(getattr(f, "name", None) or getattr(f, "path", None) or f): getattr(f, "name", None) or getattr(f, "path", None) or f for f in current_ui_files if getattr(f, "name", None) or getattr(f, "path", None) or (isinstance(f, str) and f)}
    server_filenames = {os.path.basename(p): p for p in get_server_files()}

    changes_made = False
    for name, path in server_filenames.items():
        if name not in ui_filenames:
            os.remove(path)
            changes_made = True
    for name, temp_path in ui_filenames.items():
        if name not in server_filenames:
            shutil.copy2(temp_path, os.path.join(DOCS_DIR, name))
            changes_made = True

    if changes_made:
        return "Статус: Файлы изменены. Нажмите «🔄 Применить изменения» для индексации ⚠️", get_server_files()
    return "Статус: Система готова к работе", get_server_files()

def force_reindex():
    yield "Статус: Идет векторизация документов (это займет 1-2 минуты)..."
    try:
        build_index()
        yield "Статус: Система активна · База успешно обновлена"
    except Exception as e:
        yield f"Статус: Ошибка обновления ({e})"

def init_system():
    yield "Статус: Подготовка системы..."
    for _ in range(15):
        try:
            build_index()
            yield "Статус: Система активна · Локальный контур безопасности (Air-gapped)"
            return
        except Exception:
            time.sleep(2)
    yield "Статус: Ошибка запуска базы."

def process_query(query, mode):
    if not query or not query.strip():
        return "**Введите запрос.**", ""

    result = query_system(query, mode=mode, top_k=3)
    final_answer = str(result.get("answer", ""))

    rows = []
    for source in result.get("sources", [])[:5]:
        file_name = html.escape(str(source["file"]))
        page = html.escape(str(source["page"]))
        snippet = html.escape(str(source["text_snippet"])[:180]).rstrip(". …")
        rows.append(
            f'<div class="src"><span class="src-title">{file_name}</span>'
            f'<span class="src-page">стр. {page}</span>'
            f'<div class="src-snippet">{snippet}…</div></div>'
        )
    sources_html = "".join(rows) or '<div style="padding: 20px; text-align: center; color: #757575;">Подходящих документов не найдено.</div>'
    
    return final_answer, sources_html


# --- Интерфейс Gradio ---
with gr.Blocks(theme=gr.themes.Base(primary_hue="red", neutral_hue="slate", font=SYSTEM_FONT, font_mono=SYSTEM_MONO), css=CUSTOM_CSS, js=force_light_js, title="Factory AI") as demo:

    # Шапка по центру
    with gr.Column(elem_classes="header-container"):
        gr.Markdown("# Заводской ИИ-Ассистент")
        init_status = gr.Markdown(elem_classes="status-text")

    # Основной блок (Симметричный, выровненный)
    with gr.Column():
        
        # Строка поиска
        with gr.Row(elem_classes="search-row"):
            query_input = gr.Textbox(show_label=False, container=False, lines=1, max_lines=4, elem_classes="search-box", placeholder="Спросите техническую документацию (например: допуски ГОСТ)...")
            submit_btn = gr.Button("Найти", elem_classes="go-btn")

        # Режимы работы
        mode_radio = gr.Radio(choices=[("Найти ответ", "qa"), ("Краткая сводка", "summary"), ("Нормоконтроль", "contradiction")], value="qa", show_label=False, container=False, elem_classes="modes")

        # Быстрые вопросы
        with gr.Row(elem_classes="suggested"):
            suggested_buttons = [
                gr.Button("Сводка по технике безопасности"),
                gr.Button("Найти противоречия в версиях"),
                gr.Button("Правила подготовки труб"),
            ]

        # База документов (Широкий акцентный блок)
        with gr.Column(elem_classes="file-section"):
            gr.Markdown("**Управление базой знаний**<br><span class='hint'>Перетащите файлы для загрузки. Нажмите крестик (×) для удаления из базы.</span>")
            file_manager = gr.File(value=get_server_files(), file_count="multiple", interactive=True, show_label=False)
            reindex_btn = gr.Button("🔄 Применить изменения (Переиндексировать базу)", elem_classes="reindex-btn")

        # Вывод ответа
        output_answer = gr.Markdown(value=EMPTY_ANSWER, elem_classes="answer-card")

        # Источники (Скрыты по умолчанию, чтобы не нарушать чистоту)
        with gr.Accordion("Найденные фрагменты (Контекст)", open=False, elem_classes="quiet"):
            output_sources = gr.HTML()

    # Обработчики
    run_inputs = [query_input, mode_radio]
    run_outputs = [output_answer, output_sources]

    submit_btn.click(fn=process_query, inputs=run_inputs, outputs=run_outputs)
    query_input.submit(fn=process_query, inputs=run_inputs, outputs=run_outputs)

    file_manager.change(fn=sync_files, inputs=[file_manager], outputs=[init_status, file_manager])
    reindex_btn.click(fn=force_reindex, outputs=[init_status])

    for btn in suggested_buttons:
        btn.click(fn=lambda q=btn.value: q, inputs=[], outputs=[query_input]).then(
            fn=process_query, inputs=run_inputs, outputs=run_outputs
        )

    demo.load(fn=init_system, outputs=[init_status])

if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=7860, allowed_paths=["/"])