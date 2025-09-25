import os
import faiss
import pickle
import numpy as np
from typing import List, Tuple
from sentence_transformers import SentenceTransformer
from together import Together

class RAGService:
    def __init__(self, config):
        # Use dictionary access instead of dot notation
        self.emb_model = config['EMB_MODEL']
        self.together_model = config['TOGETHER_MODEL'] 
        self.index_path = config['INDEX_PATH']
        self.meta_path = config['META_PATH']
        self.top_k = config['TOP_K']
        self.max_chars_per_chunk = config['MAX_CHARS_PER_CHUNK']
        
        self.embedder = SentenceTransformer(self.emb_model)
        self.together_client = Together(api_key=config['TOGETHER_API_KEY'])
        
        # Load existing index and metadata
        self.load_index()

    def load_index(self):
        """Load FAISS index and metadata"""
        if os.path.exists(self.meta_path):
            with open(self.meta_path, "rb") as f:
                meta = pickle.load(f)
            self.chunks = meta["chunks"]
            self.chunk_ids = meta["chunk_ids"]
        else:
            self.chunks = []
            self.chunk_ids = []

        if os.path.exists(self.index_path):
            self.index = faiss.read_index(self.index_path)
        else:
            self.index = None
        
        print("Index loaded")

        

    def build_index(self, pdf_folder, pdf_service):
        """Build FAISS index from PDFs"""
        new_chunks_total = 0

        for file in os.listdir(pdf_folder):
            if file.lower().endswith(".pdf"):
                pdf_path = os.path.join(pdf_folder, file)
                nchunks, nchunk_ids = pdf_service.extract_pdf_to_chunks(pdf_path, self.max_chars_per_chunk)
                self.chunks.extend(nchunks)
                self.chunk_ids.extend(nchunk_ids)

                # Embed only new chunks
                emb_matrix = self.embedder.encode(nchunks, convert_to_numpy=True, normalize_embeddings=True)
                dim = emb_matrix.shape[1]

                # Init FAISS index if needed
                if self.index is None:
                    self.index = faiss.IndexFlatIP(dim)

                # Add embeddings to FAISS
                self.index.add(emb_matrix)
                new_chunks_total += len(nchunks)
                print(f"Added {len(nchunks)} new chunks from {file}")
            
        print(f"Total chunks collected: {len(self.chunks)}")  # ✅ Fixed: self.chunks
        print(f"New chunks added this run: {new_chunks_total}")

        # Save index + metadata
        if self.index is not None:
            faiss.write_index(self.index, self.index_path)

        with open(self.meta_path, "wb") as f:
            pickle.dump({"chunks": self.chunks, "chunk_ids": self.chunk_ids}, f)

        print("Index and metadata saved!")

    


    def retrieve(self, query: str, context_data: str, k: int = 4) -> List[Tuple[str, str, float]]:
        """Retrieve relevant chunks"""
        if k is None:
            k = self.top_k
            
        q_vec = self.embedder.encode([query + context_data], convert_to_numpy=True, normalize_embeddings=True)
        scores, idxs = self.index.search(q_vec, k)
        
        out = []
        for score, idx in zip(scores[0], idxs[0]):
            out.append((self.chunk_ids[idx], self.chunks[idx], float(score)))
        return out

    def build_prompt(self, query: str, retrieved: List[Tuple[str, str, float]], context_data: str) -> str:
        """Build prompt with retrieved context"""
        context = "\n\n".join([f"[{cid}] {txt}" for cid, txt, _ in retrieved])
        prompt = f"""
        context: {context}
        useful data : {context_data}
        Question: {query}
        """
        return prompt

    def generate_answer(self, prompt: str, choice: int) -> str:
        """Generate answer using Together AI"""
        system_prompts = {
            1: '''You are a useful assistant for a farmer, Given the Query and the Context provided by the user, help them out.
                  the context comes from a document which outlines how to perform farming, tables will be represented as HTML and/or XLSX form.
                  moreover, additional context will be given according to thier location by the user, use that too to give a more insightful answer.
                  keep the answer simple ansd short, focus on the meat of the explaination''',
            2: '''You are a useful assistant for a farmer, Given the Query and the Context provided by the user, help them out in choosing what kind of pesticide they want.
                  the context comes from a dataset which will give recommended pesticides for certain crops and some advice on safe use of persticides
                  moreover, additional context will be given according to thier location by the user, use that too to give a more insightful answer.
                  keep the answer simple ansd short, focus on the meat of the explaination'''
        }

        resp = self.together_client.chat.completions.create(
            model=self.together_model,
            messages=[
                {"role": "system", "content": system_prompts.get(choice, system_prompts[1])},
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
            max_tokens=500,
        )
        
        return resp.choices[0].message.content

    def rag_answer(self, query: str, context_data: str, choice: int) -> str:
        """Complete RAG pipeline"""
        print(context_data)
        retrieved = self.retrieve(query, context_data)
        prompt = self.build_prompt(query, retrieved, context_data)
        answer = self.generate_answer(prompt, choice)
        return answer, retrieved
