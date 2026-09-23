import gradio as gr
import html
import os
import shutil
import time
from main import build_index, query_system

CUSTOM_CSS = """
footer {display: none !important;}
.gradio-container {max-width: 1240px !important; background: #0b1220 !important; color: #dbeafe !important;}
body {background: #070d18 !important;}
.dark-card {background: #111c2d; border: 1px solid #244568; border-radius: 10px; padding: 14px; margin: 8px 0;}
.dark-card strong {color: #93c5fd;}
.source-snippet {color: #bfdbfe; opacity: .86; margin-top: 8px; white-space: pre-wrap;}
.suggested button {background: #132945 !important; border-color: #28527d !important; color: #bfdbfe !important;}
"""


def documents_markdown():
    files = sorted(name for name in os.listdir("/app/data/docs") if os.path.isfile(os.path.join("/app/data/docs", name)))
    if not files:
        return "### 📄 Документы\nПока нет загруженных файлов."
    return "### 📄 Документы\n" + "\n".join(f"- `{name}`" for name in files)


def index_uploaded_files(files):
    if not files:
        return "Выберите хотя бы один файл.", documents_markdown()
    try:
        os.makedirs("/app/data/docs", exist_ok=True)
        for file_data in files:
            if isinstance(file_data, str):
                source = file_data
            else:
                source = getattr(file_data, "path", None) or getattr(file_data, "name", None)
            if not source:
                raise ValueError("Не удалось определить путь загруженного файла")
            shutil.copy2(source, os.path.join("/app/data/docs", os.path.basename(source)))
        build_index()
        return f"Проиндексировано файлов: {len(files)}", documents_markdown()
    except Exception as error:
        return f"Ошибка индексации: {error}", documents_markdown()


def init_system():
    yield "Инициализация моделей и индексация документов... Это может занять 1-3 минуты."
    last_error = None
    for _ in range(15):
        try:
            build_index()
            yield "✅ Система готова к работе. Документы проиндексированы автоматически."
            return
        except Exception as error:
            last_error = error
            time.sleep(2)
    yield f"Ошибка запуска индекса: {last_error}"


def process_query(query, mode):
    if not query.strip():
        return "Введите запрос.", "🧠 Модель не запускалась: введите вопрос.", ""

    result = query_system(query, mode=mode, top_k=3)

    final_answer = str(result.get("answer", ""))

    thinking = result.get("thinking") or "Модель не вернула отдельный ход мыслей; ответ сформирован по найденному контексту."
    source_cards = []
    for source in result.get("sources", [])[:5]:
        file_name = html.escape(str(source["file"]))
        page = html.escape(str(source["page"]))
        snippet = html.escape(str(source["text_snippet"])[:180])
        source_cards.append(
            f'<div class="dark-card"><strong>📄 {file_name}</strong> · стр. {page}'
            f'<div class="source-snippet">{snippet}</div></div>'
        )
    sources_html = "".join(source_cards) or '<div class="dark-card">Релевантные источники не найдены.</div>'
    return final_answer, f"🧠 {thinking}", sources_html


# --- Интерфейс Gradio ---
with gr.Blocks(theme=gr.themes.Base(), css=CUSTOM_CSS, title="Заводской ИИ-Ассистент") as demo:
    gr.Markdown("# 🏭 Заводской ИИ-Ассистент")
    gr.Markdown("Локальный поиск по технической документации. Данные не покидают предприятие.")

    with gr.Row():
        with gr.Column(scale=1):
            file_upload = gr.File(label="📂 Загрузить документы", file_types=[".pdf", ".docx", ".txt", ".jpg", ".jpeg", ".png"], file_count="multiple")
            mode_radio = gr.Radio(
                choices=[("🔍 Поиск ответа", "qa"), ("📝 Сводка", "summary"), ("⚖️ Нормоконтроль", "contradiction")],
                value="qa",
                label="Режим"
            )
            document_list = gr.Markdown(documents_markdown())
            init_status = gr.Textbox(label="Статус", interactive=False)

        with gr.Column(scale=2):
            query_input = gr.Textbox(label="Ваш вопрос", placeholder="Например: Какие допуски указаны в ГОСТ 25346?", lines=2)
            gr.Markdown("### Предложенные вопросы")
            with gr.Row(elem_classes="suggested"):
                suggested_buttons = [
                    gr.Button("Какие допуски указаны?"),
                    gr.Button("Что запрещено при работе?"),
                    gr.Button("Какие режимы сварки?"),
                ]
            submit_btn = gr.Button("▶ Получить ответ", variant="primary")
            output_answer = gr.Markdown(label="Ответ")
            with gr.Accordion("🧠 Ход мыслей ИИ", open=False):
                output_thinking = gr.Markdown()
            with gr.Accordion("📚 Источники и цитаты", open=True):
                output_sources = gr.HTML()

    submit_btn.click(
        fn=process_query,
        inputs=[query_input, mode_radio],
        outputs=[output_answer, output_thinking, output_sources]
    )

    file_upload.change(
        fn=index_uploaded_files,
        inputs=[file_upload],
        outputs=[init_status, document_list]
    )

    for suggested_button in suggested_buttons:
        suggested_button.click(fn=lambda question: question, inputs=[suggested_button], outputs=[query_input])

    demo.load(fn=init_system, outputs=[init_status])


if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=7860)
