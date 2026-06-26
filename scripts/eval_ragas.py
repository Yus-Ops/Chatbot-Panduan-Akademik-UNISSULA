# OFFLINE. pip install ragas datasets + SDK juri (mis. langchain-google-genai)
from datasets import Dataset
from ragas import evaluate
from ragas.metrics import context_precision, context_recall  # + faithfulness, answer_relevancy kalau perlu

from src.retriever import Retriever
retriever = Retriever()

# test set kecil; ground_truth wajib hanya untuk context_recall
samples = [
    {"question": "Apa visi Fakultas Teknologi Industri?",
     "ground_truth": "Menjadi Fakultas yang berkontribusi internasional pada tahun 2036 ... atas dasar nilai-nilai Islam."},
    # ... 10-20 pertanyaan
]

rows = {"question": [], "contexts": [], "ground_truth": []}
for s in samples:
    rows["question"].append(s["question"])
    rows["contexts"].append([c["text"] for c in retriever.search(s["question"])])
    rows["ground_truth"].append(s["ground_truth"])
    # rows["answer"].append(...generator...)   # hanya kalau pakai faithfulness/answer_relevancy

dataset = Dataset.from_dict(rows)
result = evaluate(
    dataset,
    metrics=[context_precision, context_recall],
    # llm=<juri dari API>, embeddings=<embedder>,   # konfigurasi sesuai versi RAGAS
)
print(result)