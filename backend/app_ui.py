import gradio as gr
import os
import shutil
from main import build_index, query_system

CUSTOM_CSS = """
footer {visibility: hidden !important;}
.gradio-container {max-width: 1200px !important;}
"""


def index_uploaded_files(files):
    if not files:
        return "Выберите хотя бы один файл."
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
        return f"Проиндексировано файлов: {len(files)}"
    except Exception as error:
        return f"Ошибка индексации: {error}"


def init_system():
    yield "Инициализация моделей и индексация документов... Это может занять 1-3 минуты."
    build_index()
    yield "✅ Система готова к работе. Загрузите документы в папку /app/data/docs или через интерфейс."


def process_query(query, mode):
    if not query.strip():
        return "Введите запрос.", ""

    result = query_system(query, mode=mode, top_k=3)

    final_answer = str(result.get("answer", ""))

    sources_md = "### 📚 Источники:\n" + "\n".join(
        f"- **{source['file']}** (Стр. {source['page']}): {source['text_snippet'][:150]}..."
        for source in result.get("sources", [])
    )
    return final_answer, sources_md


# --- Интерфейс Gradio ---
with gr.Blocks(theme=gr.themes.Default(), css=CUSTOM_CSS, title="Заводской ИИ-Ассистент") as demo:
    gr.Markdown("# 🏭 Заводской ИИ-Ассистент (Локальный)")
    gr.Markdown("Загрузите PDF, DOCX, TXT, JPG или PNG и задайте вопрос. Работает полностью офлайн.")

    with gr.Row():
        with gr.Column(scale=1):
            file_upload = gr.File(label="📂 Загрузить документы", file_types=[".pdf", ".docx", ".txt", ".jpg", ".jpeg", ".png"], file_count="multiple")
            mode_radio = gr.Radio(
                choices=[("🔍 Поиск ответа", "qa"), ("📝 Сводка", "summary"), ("⚠️ Противоречия", "contradiction")],
                value="qa",
                label="Режим"
            )
            init_status = gr.Textbox(label="Статус", interactive=False)

        with gr.Column(scale=2):
            query_input = gr.Textbox(label="Ваш вопрос", placeholder="Например: Какие допуски указаны в ГОСТ 25346?", lines=2)
            submit_btn = gr.Button("▶ Получить ответ", variant="primary")
            output_answer = gr.Markdown(label="Ответ")
            with gr.Accordion("📚 Источники и цитаты", open=True):
                output_sources = gr.Markdown()

    submit_btn.click(
        fn=process_query,
        inputs=[query_input, mode_radio],
        outputs=[output_answer, output_sources]
    )

    file_upload.change(
        fn=index_uploaded_files,
        inputs=[file_upload],
        outputs=[init_status]
    )

    demo.load(fn=init_system, outputs=[init_status])


if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=7860)
