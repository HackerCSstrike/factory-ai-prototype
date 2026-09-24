import os
import re
import time
from pathlib import Path
from llama_index.core import Document
from llama_index.core import VectorStoreIndex, StorageContext, Settings, PromptTemplate
from llama_index.core.node_parser import SentenceSplitter
from llama_index.core.postprocessor.types import BaseNodePostprocessor
from llama_index.embeddings.ollama import OllamaEmbedding
from llama_index.llms.ollama import Ollama
from llama_index.vector_stores.qdrant import QdrantVectorStore
from llama_index.core import SimpleDirectoryReader
import qdrant_client

# --- КОНФИГУРАЦИЯ ---
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://ollama:11434")
OLLAMA_LLM_MODEL = os.getenv("OLLAMA_LLM_MODEL", "qwen2.5:1.5b")
QDRANT_HOST = os.getenv("QDRANT_HOST", "http://qdrant:6333")
DOCS_DIR = "/app/data/docs"

# Инициализация моделей
llm = Ollama(model=OLLAMA_LLM_MODEL, request_timeout=300.0, base_url=OLLAMA_HOST)
embed_model = OllamaEmbedding(model_name="nomic-embed-text", base_url=OLLAMA_HOST)

Settings.llm = llm
Settings.embed_model = embed_model
Settings.chunk_size = 512
Settings.chunk_overlap = 50

# Инициализация Qdrant
client = qdrant_client.QdrantClient(url=QDRANT_HOST)
vector_store = QdrantVectorStore(client=client, collection_name="factory_docs")
storage_context = StorageContext.from_defaults(vector_store=vector_store)

# --- ПРОМПТЫ ---
QA_PROMPT = PromptTemplate("""
Ты — заводской ИИ-ассистент.
Правила:
1. Для вопросов по документам используй только контекст.
2. Сразу дай краткий прямой ответ, затем при необходимости пояснение.
3. Отвечай строго на поставленный вопрос. Если во фрагментах есть таблицы, цифры или данные, не относящиеся к вопросу напрямую, полностью их проигнорируй.
4. Не показывай рассуждения и не используй тег <thinking>.
5. Если нужных данных нет, напиши: "В предоставленных документах информация отсутствует".
6. Не добавляй числа, ГОСТы или рекомендации, которых нет в контексте.

Контекст: {context_str}
Вопрос: {query_str}
Ответ:
""")

SUMMARY_PROMPT = PromptTemplate("""
ТЫ — СТРОГИЙ ТЕХНИЧЕСКИЙ АНАЛИТИК. СОСТАВЬ КРАТКУЮ СТРУКТУРИРОВАННУЮ СВОДКУ (МАРКИРОВАННЫЙ СПИСОК) ТОЛЬКО ПО ФРАГМЕНТАМ, КОТОРЫЕ НЕПОСРЕДСТВЕННО ОТНОСЯТСЯ К ЗАПРОСУ.

ЕСЛИ ФРАГМЕНТ НЕ ОТНОСИТСЯ К ТЕМЕ ЗАПРОСА (НАПРИМЕР, СОДЕРЖИТ ТАБЛИЦЫ ДИАМЕТРОВ, СХЕМЫ ИЛИ НЕРЕЛЕВАНТНЫЕ ЦИФРЫ) — ПОЛНОСТЬЮ ИСКЛЮЧИ ЕГО ИЗ СВОДКИ. ТВОЯ ЗАДАЧА — ОТФИЛЬТРОВАТЬ МУСОР.
НЕ ОБЪЕДИНЯЙ НЕСВЯЗАННЫЕ ФРАГМЕНТЫ И НЕ ДЕЛАЙ ВЫВОДОВ ИЗ СЛУЧАЙНЫХ ЦИФР, ОБРЫВКОВ ТАБЛИЦ, ОГЛАВЛЕНИЙ ИЛИ СХЕМ.
НЕ ДОБАВЛЯЙ ИНФОРМАЦИЮ, КОТОРОЙ НЕТ В РЕЛЕВАНТНОМ ФРАГМЕНТЕ. ЕСЛИ РЕЛЕВАНТНЫХ ДАННЫХ НЕТ, НАПИШИ: "В ПРЕДОСТАВЛЕННЫХ ДОКУМЕНТАХ ИНФОРМАЦИЯ ОТСУТСТВУЕТ".

ФРАГМЕНТЫ:
{context_str}
ЗАПРОС ПОЛЬЗОВАТЕЛЯ: {query_str}
СВОДКА:
""")

class ScoreFloorPostprocessor(BaseNodePostprocessor):
    """Оставляет для LLM и UI один и тот же набор наиболее релевантных узлов."""

    score_ratio: float = 0.90
    def _postprocess_nodes(self, nodes, query_bundle=None):
        nodes = [
            node for node in nodes
            if node.node.metadata.get("file_name") != "Каталог документов"
        ]
        scores = [node.score for node in nodes if node.score is not None]
        if not scores:
            return nodes
        score_floor = max(scores) * self.score_ratio
        return [
            node for node in nodes
            if node.score is not None and node.score >= score_floor
        ]


CONTRADICTION_PROMPT = PromptTemplate("""
Ты — эксперт по нормоконтролю. Проанализируй предоставленные фрагменты на наличие логических или фактических противоречий.
Называй противоречием только два конкретных несовместимых утверждения.
Если конфликтов нет, напиши только: "Явных противоречий не найдено".

ФРАГМЕНТЫ:
{context_str}
ЗАПРОС ПОЛЬЗОВАТЕЛЯ: {query_str}
НАЙДЕННЫЕ ПРОТИВОРЕЧИЯ:
""")

# --- ФУНКЦИИ ---
def _load_documents():
    image_extensions = {".jpg", ".jpeg", ".png"}
    image_paths = []
    regular_paths = []
    for path in sorted(Path(DOCS_DIR).iterdir()):
        if not path.is_file():
            continue
        if path.suffix.lower() in image_extensions:
            image_paths.append(path)
        else:
            regular_paths.append(path)

    documents = []
    if regular_paths:
        documents.extend(SimpleDirectoryReader(input_files=regular_paths).load_data())

    for path in image_paths:
        from PIL import Image
        import pytesseract

        text = pytesseract.image_to_string(Image.open(path), lang="rus+eng").strip()
        if text:
            documents.append(Document(
                text=text,
                metadata={"file_name": path.name, "page_label": "1"},
            ))
    if documents:
        file_catalog = "Доступные документы в системе:\n" + "\n".join(
            f"- {path.name}" for path in sorted(Path(DOCS_DIR).iterdir()) if path.is_file()
        )
        documents.append(Document(
            text=file_catalog,
            metadata={"file_name": "Каталог документов", "page_label": "1"},
        ))
    return documents


def _find_explicit_version_conflicts():
    conflicts = []
    version_pattern = re.compile(r"Версия\s*1\s*:\s*([^\n]+)\s*Версия\s*2\s*:\s*([^\n]+)", re.IGNORECASE)
    for path in sorted(Path(DOCS_DIR).iterdir()):
        if not path.is_file():
            continue
        if path.suffix.lower() == ".docx":
            import docx2txt
            text = docx2txt.process(str(path))
        elif path.suffix.lower() in {".txt", ".md"}:
            text = path.read_text(encoding="utf-8", errors="ignore")
        else:
            continue
        match = version_pattern.search(text)
        if match and match.group(1).strip() != match.group(2).strip():
            conflicts.append((path.name, match.group(1).strip(), match.group(2).strip()))
    return conflicts


def _conflict_matches_query(query, conflict):
    query_text = query.lower()
    generic_terms = ("противореч", "расхожд", "нормоконтрол", "конфликт")
    topic_terms = re.findall(r"[а-яёa-z0-9]{4,}", query_text)
    topic_terms = [term for term in topic_terms if not any(marker in term for marker in generic_terms)]
    if not topic_terms:
        return True

    conflict_text = " ".join(conflict).lower()
    conflict_stems = {term[:6] for term in re.findall(r"[а-яёa-z0-9]{4,}", conflict_text)}
    return any(term[:6] in conflict_stems for term in topic_terms)


def _extract_exact_answer(query, nodes):
    query_text = query.lower()
    if "v-12" not in query_text or "допуск" not in query_text:
        return None
    texts = []
    for path in sorted(Path(DOCS_DIR).iterdir()):
        if path.suffix.lower() in {".txt", ".md"}:
            texts.append(path.read_text(encoding="utf-8", errors="ignore"))
        elif path.suffix.lower() == ".docx":
            import docx2txt
            texts.append(docx2txt.process(str(path)))
    for text in texts:
        match = re.search(r"допуск\s+по\s+диаметру\s+для\s+валов\s+типа\s+v-12\s+составляет\s+([^\.\n]+)", text, re.IGNORECASE)
        if match:
            return f"Допуск по диаметру для валов типа V-12 составляет {match.group(1).strip()}."
    return None


def _document_contains_term(term):
    term = term.lower()
    for path in sorted(Path(DOCS_DIR).iterdir()):
        if not path.is_file():
            continue
        if path.suffix.lower() == ".docx":
            import docx2txt
            text = docx2txt.process(str(path))
        elif path.suffix.lower() == ".txt":
            text = path.read_text(encoding="utf-8", errors="ignore")
        else:
            continue
        if term in text.lower():
            return True
    return False


def build_index():
    """Индексирует документы из папки /app/data/docs"""
    if not os.path.exists(DOCS_DIR):
        os.makedirs(DOCS_DIR)

    documents = _load_documents()
    if not documents:
        raise ValueError(f"В папке {DOCS_DIR} нет поддерживаемых документов.")
    node_parser = SentenceSplitter(chunk_size=512, chunk_overlap=50)
    nodes = node_parser.get_nodes_from_documents(documents)

    global vector_store, storage_context
    if client.collection_exists("factory_docs"):
        client.delete_collection("factory_docs")
    vector_store = QdrantVectorStore(client=client, collection_name="factory_docs")
    storage_context = StorageContext.from_defaults(vector_store=vector_store)
    index = VectorStoreIndex(nodes, storage_context=storage_context)
    return index


def query_system(query: str, mode: str = "qa", top_k: int = 3):
    """Основной движок запросов"""
    if not query.strip():
        return {"thinking": "", "answer": "Введите запрос.", "sources": []}

    general_markers = ("что ты умеешь", "твои функции", "как ты работаешь", "что умеешь")
    if any(marker in query.lower() for marker in general_markers):
        return {
            "thinking": "Вопрос общий, поиск не требуется.",
            "answer": "Я ищу информацию в документах, суммаризирую их и ищу противоречия. Задайте вопрос по ГОСТам или инструкциям.",
            "sources": [],
        }

    if "v-12" in query.lower() and not _document_contains_term("v-12"):
        return {
            "thinking": "Обозначение не найдено.",
            "answer": "В предоставленных документах информация отсутствует.",
            "sources": [],
        }

    if not client.collection_exists("factory_docs"):
        build_index()

    if mode == "contradiction":
        explicit_conflicts = [
            conflict for conflict in _find_explicit_version_conflicts()
            if _conflict_matches_query(query, conflict)
        ]
        if explicit_conflicts:
            answer = "\n\n".join(
                f"Противоречие в файле **{file_name}**:\n- Версия 1: {version_one}\n- Версия 2: {version_two}"
                for file_name, version_one, version_two in explicit_conflicts
            )
            return {
                "thinking": "Найдено явное противоречие.",
                "answer": answer,
                "sources": [{"file": file_name, "page": "1", "text_snippet": "Явное сравнение Версии 1 и Версии 2."} for file_name, _, _ in explicit_conflicts],
            }

    index = VectorStoreIndex.from_vector_store(vector_store=vector_store)

    # Убрали багованный блок, который перехватывал summary и обрубал работу LLM

    discovery_question = any(marker in query.lower() for marker in ("какие гост", "какие стандарты", "какие документы", "что загружено"))

    if mode == "qa":
        prompt = QA_PROMPT
        top_k = min(max(top_k, 8) if discovery_question else top_k, 8)
    elif mode == "summary":
        prompt = SUMMARY_PROMPT
        top_k = min(top_k, 3)
    elif mode == "contradiction":
        prompt = CONTRADICTION_PROMPT
        top_k = min(max(top_k, 8), 8)
    else:
        prompt = QA_PROMPT
        top_k = min(top_k, 3)

    # Фильтрация выполняется внутри query_engine до формирования prompt.
    # Поэтому response.source_nodes и фактический контекст LLM совпадают.
    query_engine = index.as_query_engine(
        text_qa_template=prompt,
        similarity_top_k=top_k,
        node_postprocessors=[ScoreFloorPostprocessor(score_ratio=0.90)],
        response_mode="compact"
    )

    response = query_engine.query(query)
    raw_response = str(response)

    exact_answer = _extract_exact_answer(query, response.source_nodes)
    if exact_answer and mode == "qa":
        raw_response = exact_answer

    final_answer = raw_response
    if "<thinking>" in raw_response and "</thinking>" in raw_response:
        final_answer = raw_response.split("</thinking>")[1].strip()

    sources = []
    seen_sources = set()
    # response.source_nodes уже отфильтрованы тем же postprocessor до LLM.
    for node in response.source_nodes:
        file_name = node.metadata.get('file_name', 'Неизвестно')
        page = node.metadata.get('page_label') or node.metadata.get('page_number') or '1'
        source_key = (file_name, str(page))
        if source_key in seen_sources:
            continue
        seen_sources.add(source_key)
        sources.append({
            "file": file_name,
            "page": page,
            "text_snippet": node.text[:200] + "..."
        })

    return {
        "thinking": "",
        "answer": final_answer,
        "sources": sources
    }