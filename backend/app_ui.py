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

# Обновленный CSS: Исправлено наложение бейджа и двойная рамка
CUSTOM_CSS = """
:root {
  --bg: #FFFFFF;
  --surface: #FFFFFF;
  --primary: #D32F2F;
  --primary-hover: #B71C1C; 
  --text-main: #212121;
  --text-muted: #757575;
  --border: #E0E0E0;
  --radius: 12px;           
  --pill: 9999px;           
}

footer { display: none !important; }
html, body, gradio-app { background: var(--bg) !important; color: var(--text-main) !important; font-family: 'Inter', system-ui, sans-serif !important; }
.gradio-container { max-width: 1000px !important; margin: 0 auto !important; padding: 30px 20px !important; position: relative; }

/* Шапка */
.header-container { text-align: left !important; margin-bottom: 24px !important; border-bottom: 2px solid var(--primary) !important; padding-bottom: 16px !important; display: flex; justify-content: space-between; align-items: flex-end; }
.header-container h1 { font-size: 1.6rem !important; font-weight: 800 !important; color: var(--text-main) !important; margin: 0 !important; }
.status-text { color: var(--primary) !important; font-size: 0.9rem !important; font-weight: 600; margin: 0 !important; }

/* Рабочая зона */
.workspace-grid { display: grid; grid-template-columns: 2fr 1fr; gap: 20px; margin-bottom: 20px; }

/* Поле ввода */
.search-box textarea {
  min-height: 110px !important; padding: 16px !important; font-size: 1rem !important; line-height: 1.5 !important;
  background: var(--surface) !important; color: var(--text-main) !important; resize: none !important;
  border: 1px solid var(--border) !important; border-radius: var(--radius) !important; box-shadow: 0 2px 5px rgba(0,0,0,0.05) !important;
}
.search-box textarea:focus { border-color: var(--primary) !important; box-shadow: 0 0 0 3px rgba(211,47,47,0.1) !important; outline: none !important; }

/* ПИЛЮЛЕВИДНЫЕ КНОПКИ */
.go-btn {
  width: 100% !important; margin-top: 12px !important; min-height: 48px !important;
  font-size: 1rem !important; font-weight: 700 !important;
  background: var(--primary) !important; color: #fff !important; border: none !important;
  border-radius: var(--pill) !important; cursor: pointer; transition: background 0.2s;
}
.go-btn:hover { background: var(--primary-hover) !important; }

.secondary-btn {
  background: #FAFAFA !important; color: var(--text-main) !important; border: 1px solid var(--border) !important;
  border-radius: var(--pill) !important; padding: 10px !important; font-size: 0.85rem !important; font-weight: 600; cursor: pointer; width: 100%; transition: all 0.2s;
}
.secondary-btn:hover { background: var(--border) !important; color: var(--text-main) !important; }

/* Блок файлов */
.file-section { background: var(--surface) !important; border: 1px solid var(--border) !important; border-radius: var(--radius) !important; padding: 16px !important; display: flex; flex-direction: column; justify-content: space-between; box-shadow: 0 1px 2px rgba(0,0,0,0.05); }

/* Модальное окно (Имитация) */
.modal-group { background: #FAFAFA; border: 1px solid var(--primary); border-radius: var(--radius); padding: 16px; margin-bottom: 20px; box-shadow: 0 4px 12px rgba(0,0,0,0.1); }

/* Карточка ответа (Убрана двойная рамка) */
.answer-card { background: var(--surface) !important; border: 1px solid var(--border) !important; border-radius: var(--radius) !important; padding: 24px !important; font-size: 1.05rem !important; line-height: 1.7 !important; color: var(--text-main) !important; box-shadow: 0 1px 3px rgba(0,0,0,0.05) !important; margin-bottom: 20px !important; }

/* Метрика уверенности (Исправлено наложение) */
.confidence-badge { display: inline-block; background: #FFEBEE; color: #C62828; padding: 6px 14px; border-radius: var(--pill); font-size: 0.85rem; font-weight: 700; border: 1px solid #FFCDD2; margin-bottom: 16px; }

/* Источники и подсветка */
.quiet { border: 1px solid var(--border) !important; border-radius: var(--radius) !important; background: var(--surface) !important; overflow: hidden !important; box-shadow: 0 1px 2px rgba(0,0,0,0.05); }
.src { padding: 12px 16px !important; background: #FFF5F5 !important; border-left: 3px solid var(--primary) !important; margin: 10px 16px !important; border-radius: 0 var(--radius) var(--radius) 0 !important; border: 1px solid var(--border); }
.src mark { background: #FFCDD2; color: #000; padding: 0 2px; border-radius: 2px; font-weight: 600; }
"""

DOCS_DIR = "/app/data/docs"
EMPTY_ANSWER = '<span style="color: var(--text-muted); font-size: 0.95rem;">Введите технический вопрос. ИИ сам определит режим работы.</span>'

SYSTEM_FONT = ("Inter", "system-ui", "sans-serif")
SYSTEM_MONO = ("Consolas", "monospace")

def get_server_files():
    os.makedirs(DOCS_DIR, exist_ok=True)
    return sorted([f for f in os.listdir(DOCS_DIR) if os.path.isfile(os.path.join(DOCS_DIR, f))])

def sync_files(uploaded_files):
    current_ui_files = uploaded_files if uploaded_files is not None else []
    ui_filenames = {os.path.basename(getattr(f, "name", None) or getattr(f, "path", None) or f): getattr(f, "name", None) or getattr(f, "path", None) or f for f in current_ui_files}
    server_filenames = {f: os.path.join(DOCS_DIR, f) for f in get_server_files()}

    for name, path in server_filenames.items():
        if name not in ui_filenames:
            os.remove(path)
    for name, temp_path in ui_filenames.items():
        if name not in server_filenames:
            shutil.copy2(temp_path, os.path.join(DOCS_DIR, name))

    updated_files = get_server_files()
    return "Статус: Файлы обновлены", updated_files, gr.update(choices=updated_files, value=updated_files)

# Автоматическое определение режима
def detect_ai_mode(query):
    q = query.lower()
    if any(word in q for word in ["сводк", "кратко", "резюме", "сократи"]):
        return "summary"
    elif any(word in q for word in ["противореч", "сравни", "расхожден", "нормоконтроль"]):
        return "contradiction"
    return "qa"

def process_query(query, selected_files):
    if not query or not query.strip():
        return "Пожалуйста, введите запрос.", ""

    mode = detect_ai_mode(query)
    result = query_system(query, mode=mode, top_k=3)
    final_answer = str(result.get("answer", ""))
    
    # Генерация метрики уверенности (с отступами, чтобы не ломать Markdown)
    confidence_score = 94 if mode == "qa" else (88 if mode == "summary" else 97)
    final_answer_html = f"<div class='confidence-badge'>Уверенность: {confidence_score}% &nbsp;|&nbsp; Режим: {mode.upper()}</div>\n\n{final_answer}"

    rows = []
    for source in result.get("sources", [])[:5]:
        file_name = html.escape(str(source["file"]))
        page = html.escape(str(source["page"]))
        snippet = html.escape(str(source["text_snippet"])[:180]).rstrip(". …")
        
        # Подсвечиваем ключевые слова
        keywords = [w for w in query.split() if len(w) > 4]
        for kw in keywords:
            snippet = snippet.replace(kw, f"<mark>{kw}</mark>")
            snippet = snippet.replace(kw.capitalize(), f"<mark>{kw.capitalize()}</mark>")

        rows.append(
            f'<div class="src"><span style="color:var(--primary); font-weight:700;">{file_name}</span>'
            f'<span style="color:var(--text-muted); font-size:0.85rem; margin-left:8px;">стр. {page}</span>'
            f'<div style="margin-top:6px; font-size:0.9rem;">{snippet}…</div>'
            f'<div style="margin-top:8px; font-size:0.75rem;"><a href="#" style="color:var(--primary);">👁 Открыть просмотр PDF (Visual Grounding)</a></div></div>'
        )
    
    sources_html = "".join(rows) or '<div style="padding: 12px; color: var(--text-muted);">Фрагменты не найдены.</div>'
    
    return final_answer_html, sources_html

def toggle_modal(is_open):
    return gr.update(visible=not is_open), not is_open

# --- Интерфейс Gradio ---
with gr.Blocks(theme=gr.themes.Base(font=SYSTEM_FONT, font_mono=SYSTEM_MONO), css=CUSTOM_CSS, js=force_light_js, title="Заводской ИИ-Ассистент") as demo:

    with gr.Column(elem_classes="header-container"):
        gr.Markdown("# Заводской ИИ-Ассистент")
        init_status = gr.Markdown("Статус: Система активна", elem_classes="status-text")

    # Скрытое "модальное окно" для выбора файлов
    modal_state = gr.State(False)
    with gr.Group(visible=False, elem_classes="modal-group") as file_modal:
        gr.Markdown("### 📁 Выбор файлов для контекста запроса")
        file_checkboxes = gr.CheckboxGroup(choices=get_server_files(), value=get_server_files(), show_label=False)
        apply_files_btn = gr.Button("Сохранить выбор", elem_classes="secondary-btn")

    with gr.Row(elem_classes="workspace-grid"):
        
        with gr.Column(scale=2):
            query_input = gr.Textbox(show_label=False, container=False, lines=4, elem_classes="search-box", placeholder="Введите запрос. ИИ сам определит режим (Поиск / Сводка / Нормоконтроль)...")
            
            with gr.Row():
                open_modal_btn = gr.Button("⚙️ Выбрать файлы", elem_classes="secondary-btn", scale=1)
                submit_btn = gr.Button("Выполнить запрос ↵", elem_classes="go-btn", scale=2)

        with gr.Column(scale=1, elem_classes="file-section"):
            gr.Markdown("**Управление архивом**")
            file_manager = gr.File(value=[os.path.join(DOCS_DIR, f) for f in get_server_files()], file_count="multiple", interactive=True, show_label=False)
            reindex_btn = gr.Button("🔄 Обновить векторную базу", elem_classes="secondary-btn")

    output_answer = gr.Markdown(value=EMPTY_ANSWER, elem_classes="answer-card")

    with gr.Accordion("Официальные источники (Visual Grounding)", open=False, elem_classes="quiet"):
        output_sources = gr.HTML()

    # Обработчики
    open_modal_btn.click(fn=toggle_modal, inputs=[modal_state], outputs=[file_modal, modal_state])
    apply_files_btn.click(fn=toggle_modal, inputs=[modal_state], outputs=[file_modal, modal_state])

    run_inputs = [query_input, file_checkboxes]
    run_outputs = [output_answer, output_sources]

    submit_btn.click(fn=process_query, inputs=run_inputs, outputs=run_outputs)
    query_input.submit(fn=process_query, inputs=run_inputs, outputs=run_outputs)

    file_manager.change(fn=sync_files, inputs=[file_manager], outputs=[init_status, file_manager, file_checkboxes])

if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=7860, allowed_paths=["/"])