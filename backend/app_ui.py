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

# Дизайн: один экран — одно действие. Поиск в центре, всё остальное тише.
# Шрифты только системные (без Google Fonts): сеть закрыта, внешние шрифты не загрузятся.
CUSTOM_CSS = """
:root {
  --bg: #EEF0EE; --surface: #FFFFFF; --ink: #1B2226; --ink-2: #4A565C;
  --line: #D5DAD7; --steel: #0F5C6E; --steel-dark: #0B4655; --signal: #F2A900;
}
footer { display: none !important; }
html, body, gradio-app { background: var(--bg) !important; }
.gradio-container { background: transparent !important; max-width: 1000px !important; margin: 0 auto !important; padding: 0 24px 48px !important; color: var(--ink); }
.gradio-container .prose { color: var(--ink) !important; }

/* Шапка */
.gradio-container .topbar { align-items: center !important; padding-top: 18px; gap: 12px; }
.gradio-container .topbar .block { background: transparent !important; border: none !important; box-shadow: none !important; padding: 0 !important; }
.gradio-container .topbar h1 { font-size: 1.1rem !important; font-weight: 700 !important; margin: 0 !important; }
.gradio-container .topbar .prose p { margin: 0 !important; }
.gradio-container .status { text-align: right; }
.gradio-container .status, .gradio-container .status * { color: var(--ink-2) !important; font-size: 0.9rem !important; }

/* Главный блок */
.gradio-container .hero { padding: 36px 0 4px; gap: 0 !important; }
.gradio-container .hero > .block, .gradio-container .hero .prose { background: transparent !important; border: none !important; box-shadow: none !important; padding: 0 !important; }
.gradio-container .hero h2 { font-size: clamp(1.5rem, 1.1rem + 1.2vw, 2rem) !important; font-weight: 700 !important; letter-spacing: -0.01em; margin: 0 0 16px !important; }

/* Строка поиска: поле и кнопка одной высоты, склеены */
.gradio-container .search-row { gap: 0 !important; flex-wrap: nowrap !important; align-items: stretch !important; }
.gradio-container .search-box { border-radius: 0 !important; flex: 1 1 auto !important; min-width: 0 !important; background: transparent !important; border: none !important; box-shadow: none !important; padding: 0 !important; }
.gradio-container .search-box label { padding: 0 !important; background: transparent !important; border: none !important; box-shadow: none !important; height: 100%; }
.gradio-container .search-box textarea {
  min-height: 56px !important; padding: 15px 18px !important; font-size: 1.125rem !important; line-height: 1.4 !important;
  background: var(--surface) !important; color: var(--ink) !important; resize: none !important;
  border-width: 2px 0 2px 0 !important; border-style: solid !important; border-color: #1B2226 !important; border-radius: 0 !important; box-shadow: none !important;
}
.gradio-container .search-box textarea:focus { outline: none !important; box-shadow: inset 0 0 0 3px var(--signal) !important; }
.gradio-container .go-btn {
  flex: 0 0 140px !important; min-width: 140px !important; min-height: 56px !important;
  font-size: 1.1rem !important; font-weight: 600 !important;
  background: var(--steel) !important; color: #fff !important; border: 2px solid var(--steel) !important;
  border-radius: 0 10px 10px 0 !important; box-shadow: none !important;
}
.gradio-container .go-btn:hover { background: var(--steel-dark) !important; border-color: var(--steel-dark) !important; }
.gradio-container .go-btn:focus-visible { outline: 3px solid var(--signal) !important; outline-offset: 2px; }

/* Скрепка: загрузка документов рядом с полем ввода */
.gradio-container .attach-btn {
  flex: 0 0 56px !important; min-width: 56px !important; max-width: 56px !important; min-height: 56px !important; padding: 0 !important;
  font-size: 1.3rem !important; background: var(--surface) !important; color: var(--ink) !important;
  border: 2px solid #1B2226 !important; border-right: none !important; border-radius: 10px 0 0 10px !important; box-shadow: none !important;
}
.gradio-container .attach-btn:hover { background: #E6F0F2 !important; }
.gradio-container .attach-btn:focus-visible { outline: 3px solid var(--signal) !important; outline-offset: 2px; }

/* Режимы */
.gradio-container .modes { margin-top: 14px !important; background: transparent !important; border: none !important; box-shadow: none !important; padding: 0 !important; }
.gradio-container .modes .wrap { gap: 8px !important; flex-wrap: wrap !important; }
.gradio-container .modes label {
  position: relative; display: flex; align-items: center; cursor: pointer;
  padding: 9px 16px !important; font-size: 1rem !important; box-shadow: none !important;
  background: var(--surface) !important; border: 1.5px solid var(--line) !important; border-radius: 8px !important; color: var(--ink-2) !important;
}
.gradio-container .modes label span { margin: 0 !important; color: inherit !important; font-size: inherit !important; }
.gradio-container .modes label input { position: absolute !important; opacity: 0 !important; width: 1px !important; height: 1px !important; margin: 0 !important; pointer-events: none; }
.gradio-container .modes label.selected { background: var(--ink) !important; border-color: var(--ink) !important; color: #fff !important; font-weight: 600; }
.gradio-container .modes label:focus-within { outline: 3px solid var(--signal); outline-offset: 2px; }

/* Частые запросы */
.gradio-container .suggested { gap: 8px !important; margin-top: 14px !important; flex-wrap: wrap !important; }
.gradio-container .suggested button {
  flex: 0 0 auto !important; width: auto !important; min-width: 0 !important;
  background: var(--surface) !important; color: var(--steel) !important; border: 1px solid var(--line) !important;
  border-radius: 999px !important; padding: 7px 14px !important; font-size: 0.95rem !important; box-shadow: none !important;
}
.gradio-container .suggested button:hover { border-color: var(--steel) !important; background: #E6F0F2 !important; }

/* Ответ: одна карточка (класс стоит и на блоке, и на внутреннем .prose — стилизуем раздельно) */
.gradio-container .answer-card.block { background: var(--surface) !important; border: 1px solid var(--line) !important; border-radius: 10px !important; padding: 22px 26px !important; margin-top: 28px !important; box-shadow: none !important; }
.gradio-container .prose.answer-card { background: transparent !important; border: none !important; box-shadow: none !important; padding: 0 !important; margin: 0 !important; font-size: 1.0625rem; line-height: 1.65; max-width: 75ch; }
.gradio-container .prose.answer-card p { margin: 0 0 0.8em; }
.gradio-container .prose.answer-card p:last-child { margin-bottom: 0; }

/* Источники */
.src { padding: 14px 2px; border-bottom: 1px solid var(--line); }
.src:last-child { border-bottom: none; }
.src-title { font-weight: 600; color: var(--ink); }
.src-page { color: var(--steel); font-weight: 600; margin-left: 8px; white-space: nowrap; }
.src-snippet { color: var(--ink-2); font-size: 0.95rem; line-height: 1.5; margin-top: 4px; white-space: pre-wrap; max-width: 80ch; }
.hint { color: var(--ink-2); }

/* Второстепенные разделы */
.gradio-container .quiet { background: transparent !important; border: none !important; border-top: 1px solid var(--line) !important; border-radius: 0 !important; box-shadow: none !important; margin-top: 12px; }
.gradio-container .quiet .label-wrap { padding: 14px 2px !important; }
.gradio-container .quiet .label-wrap span { font-size: 1rem !important; font-weight: 600 !important; color: var(--ink) !important; }

@media (max-width: 640px) {
  .gradio-container { padding: 0 14px 32px !important; }
  .gradio-container .topbar { flex-wrap: wrap !important; }
  .gradio-container .status { text-align: left !important; }
  .gradio-container .go-btn { flex-basis: 96px !important; min-width: 96px !important; }
  .gradio-container .answer-card.block { padding: 16px 16px !important; }
}
@media (prefers-reduced-motion: reduce) { * { transition: none !important; animation: none !important; } }
"""

DOCS_DIR = "/app/data/docs"
EMPTY_ANSWER = '<span class="hint">Введите вопрос и нажмите «Найти». Ответ появится здесь вместе с документами, из которых он взят.</span>'

# Системные шрифты вместо Google Fonts (в закрытом контуре внешние шрифты не грузятся)
SYSTEM_FONT = ("Segoe UI", "Roboto", "Helvetica Neue", "Arial", "sans-serif")
SYSTEM_MONO = ("Consolas", "Menlo", "Courier New", "monospace")


def get_server_files():
    """Возвращает актуальный список файлов на сервере."""
    os.makedirs(DOCS_DIR, exist_ok=True)
    return sorted([os.path.join(DOCS_DIR, f) for f in os.listdir(DOCS_DIR) if os.path.isfile(os.path.join(DOCS_DIR, f))])


def sync_files(uploaded_files):
    """Синхронизирует UI компонент с папкой на сервере (загрузка и удаление на крестик)."""
    current_ui_files = uploaded_files if uploaded_files is not None else []
    ui_filenames = {}

    for f in current_ui_files:
        path = getattr(f, "name", None) or getattr(f, "path", None) or (f if isinstance(f, str) else None)
        if path:
            ui_filenames[os.path.basename(path)] = path

    server_files = get_server_files()
    server_filenames = {os.path.basename(p): p for p in server_files}

    changes_made = False

    # Файл есть на сервере, но нет в UI (нажали крестик) -> удаляем
    for name, path in server_filenames.items():
        if name not in ui_filenames:
            os.remove(path)
            changes_made = True

    # Файл есть в UI, но нет на сервере (загрузили новый) -> копируем
    for name, temp_path in ui_filenames.items():
        if name not in server_filenames:
            shutil.copy2(temp_path, os.path.join(DOCS_DIR, name))
            changes_made = True

    if changes_made:
        try:
            build_index()
            return "● База документов обновлена", get_server_files()
        except Exception as e:
            return f"● Ошибка обновления: {e}", get_server_files()

    return "● Система готова к работе", get_server_files()


def upload_files(files):
    """Скрепка: копирует выбранные файлы в базу и пересобирает индекс."""
    if not files:
        return "● Система готова к работе", get_server_files()
    os.makedirs(DOCS_DIR, exist_ok=True)
    for f in files:
        path = getattr(f, "name", None) or (f if isinstance(f, str) else None)
        if path:
            shutil.copy2(path, os.path.join(DOCS_DIR, os.path.basename(path)))
    try:
        build_index()
        return f"● Добавлено файлов: {len(files)}", get_server_files()
    except Exception as e:
        return f"● Ошибка обновления: {e}", get_server_files()


def init_system():
    yield "● Подготовка системы…"
    for _ in range(15):
        try:
            build_index()
            yield "● Система готова · работает без интернета"
            return
        except Exception:
            time.sleep(2)
    yield "● Ошибка запуска базы. Обратитесь в ИТ-отдел."


def process_query(query, mode):
    if not query or not query.strip():
        return "**Введите вопрос.** Например: «Какая допустимая толщина металла по ГОСТ?»", "", ""

    result = query_system(query, mode=mode, top_k=3)
    final_answer = str(result.get("answer", ""))
    thinking = result.get("thinking") or "Ответ сформирован напрямую из найденных документов."

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
    sources_html = "".join(rows) or (
        '<div class="src hint">Подходящих документов не найдено. '
        'Переформулируйте вопрос или загрузите нужный документ.</div>'
    )
    return final_answer, thinking, sources_html


# --- Интерфейс Gradio ---
with gr.Blocks(
    theme=gr.themes.Base(primary_hue="cyan", neutral_hue="slate", font=SYSTEM_FONT, font_mono=SYSTEM_MONO),
    css=CUSTOM_CSS, js=force_light_js, title="Заводской ИИ-Ассистент",
) as demo:

    with gr.Row(elem_classes="topbar"):
        gr.Markdown("# Заводской ИИ-ассистент")
        init_status = gr.Markdown(elem_classes="status")

    with gr.Column(elem_classes="hero"):
        gr.Markdown("## Что нужно найти в документации?")

        with gr.Row(elem_classes="search-row"):
            attach_btn = gr.UploadButton("📎", file_count="multiple", scale=0, min_width=56, elem_classes="attach-btn")
            query_input = gr.Textbox(
                show_label=False, container=False, lines=1, max_lines=4, scale=5, elem_classes="search-box",
                placeholder="Например: какие требования к толщине металла по ГОСТ?",
            )
            submit_btn = gr.Button("Найти", scale=1, elem_classes="go-btn")

        mode_radio = gr.Radio(
            choices=[("Найти ответ", "qa"), ("Кратко изложить", "summary"), ("Проверить на противоречия", "contradiction")],
            value="qa", show_label=False, container=False, elem_classes="modes",
        )

        with gr.Row(elem_classes="suggested"):
            suggested_buttons = [
                gr.Button("Сводка по технике безопасности", size="sm"),
                gr.Button("Найти противоречия в регламентах", size="sm"),
                gr.Button("Какие режимы работы допустимы?", size="sm"),
            ]

    output_answer = gr.Markdown(value=EMPTY_ANSWER, elem_classes="answer-card")

    with gr.Accordion("Источники", open=True, elem_classes="quiet"):
        output_sources = gr.HTML()

    with gr.Accordion("Как получен ответ", open=False, elem_classes="quiet"):
        output_thinking = gr.Markdown()

    with gr.Accordion("Загруженные документы", open=False, elem_classes="quiet"):
        gr.Markdown("Добавляйте документы скрепкой рядом с полем поиска. Чтобы удалить документ, нажмите **×** рядом с названием.")
        file_manager = gr.File(value=get_server_files(), file_count="multiple", interactive=True, show_label=False)

    # Обработчики
    run_inputs = [query_input, mode_radio]
    run_outputs = [output_answer, output_thinking, output_sources]

    submit_btn.click(fn=process_query, inputs=run_inputs, outputs=run_outputs)
    query_input.submit(fn=process_query, inputs=run_inputs, outputs=run_outputs)

    attach_btn.upload(fn=upload_files, inputs=[attach_btn], outputs=[init_status, file_manager])
    file_manager.change(fn=sync_files, inputs=[file_manager], outputs=[init_status, file_manager])

    # Подсказка подставляет текст и сразу запускает поиск
    for btn in suggested_buttons:
        btn.click(fn=lambda q=btn.value: q, inputs=[], outputs=[query_input]).then(
            fn=process_query, inputs=run_inputs, outputs=run_outputs
        )

    demo.load(fn=init_system, outputs=[init_status])


if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=7860, allowed_paths=["/"])