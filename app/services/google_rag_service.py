import os
import faiss
import pickle
import numpy as np
from typing import List, Tuple
from sentence_transformers import SentenceTransformer
import google.generativeai as genai


class ImprovedGoogleRAGService:
    def __init__(self, config):
        # Configuration
        self.emb_model = config['EMB_MODEL']
        self.index_path = config['INDEX_PATH']
        self.meta_path = config['META_PATH']
        self.top_k = config['TOP_K']
        self.max_chars_per_chunk = config['MAX_CHARS_PER_CHUNK']
        self.google_api_key = config['GOOGLE_API_KEY']
        self.google_model = config.get('GOOGLE_MODEL', 'gemini-2.5-flash')
        self.context_window = config.get('CONTEXT_WINDOW', 5)
        
        # Initialize components
        self.embedder = SentenceTransformer(self.emb_model)
        genai.configure(api_key=self.google_api_key)
        self.llm = genai.GenerativeModel(self.google_model)
        
        # Chat session for proper conversation memory
        self.chat_session = None
        self.conversation_history = []  # Current active session history
        
        # Session management (managed by main.py)
        self.user_sessions = {}
        self.session_metadata = {}
        
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

                self.index.add(emb_matrix)
                new_chunks_total += len(nchunks)
                print(f"Added {len(nchunks)} new chunks from {file}")
            
        print(f"Total chunks collected: {len(self.chunks)}")
        print(f"New chunks added this run: {new_chunks_total}")

        # Save index + metadata
        if self.index is not None:
            faiss.write_index(self.index, self.index_path)

        with open(self.meta_path, "wb") as f:
            pickle.dump({"chunks": self.chunks, "chunk_ids": self.chunk_ids}, f)

        print("Index and metadata saved!")

    def retrieve_context_aware(self, query: str, context_data: str, k: int = 4) -> List[Tuple[str, str, float]]:
        """FIXED: Enhanced retrieval that properly uses conversation history"""
        if k is None:
            k = self.top_k
        
        enhanced_query = query
        
        # Build enhanced query with conversation context
        if self.conversation_history and len(self.conversation_history) > 0:
            print(f"DEBUG: Found {len(self.conversation_history)} conversation entries")
            
            # Extract actual user queries from conversation history
            recent_context = []
            for exchange in self.conversation_history[-2:]:  # Last 2 exchanges
                user_query = exchange.get('user', '').strip()
                
                # FIXED: Store and use the original user query, not the full prompt
                if len(user_query) < 200 and user_query:
                    recent_context.append(user_query)
                    print(f"DEBUG: Adding context: '{user_query}'")
            
            if recent_context:
                # Combine recent context with current query for better retrieval
                enhanced_query = " ".join(recent_context + [query])
                print(f"DEBUG: Enhanced query with context: '{enhanced_query}'")
            
            # FIXED: Extract key topics from assistant responses for better context
            topic_keywords = []
            if self.conversation_history:
                last_response = self.conversation_history[-1].get('assistant', '').lower()
                # Extract relevant agricultural terms
                agricultural_terms = [
                    'tomato', 'plant', 'plants', 'leaves', 'yellow', 'yellowing', 'disease', 'diseases',
                    'nutrient', 'nutrients', 'deficiency', 'magnesium', 'zinc', 'boron', 'fertilizer',
                    'crop', 'crops', 'soil', 'growth', 'farming', 'agriculture', 'pest', 'pesticide',
                    'irrigation', 'water', 'harvest', 'seed', 'planting', 'fertilization'
                ]
                
                for term in agricultural_terms:
                    if term in last_response and term.lower() not in enhanced_query.lower():
                        topic_keywords.append(term)
                        if len(topic_keywords) >= 3:  # Limit to top 3 terms
                            break
                
                if topic_keywords:
                    enhanced_query += " " + " ".join(topic_keywords)
                    print(f"DEBUG: Added topic keywords: {topic_keywords}")
        
        # Create search vector with enhanced query + location context
        search_text = enhanced_query + " " + context_data
        print(f"DEBUG: Final search text: '{search_text[:200]}...'")
        
        q_vec = self.embedder.encode([search_text], convert_to_numpy=True, normalize_embeddings=True)
        scores, idxs = self.index.search(q_vec, k)
        
        out = []
        for score, idx in zip(scores[0], idxs[0]):
            chunk_id = self.chunk_ids[idx]
            chunk_text = self.chunks[idx]
            out.append((chunk_id, chunk_text, float(score)))
            print(f"DEBUG: Retrieved {chunk_id}: score={score:.4f}, preview='{chunk_text[:100]}'")
        
        return out

    def retrieve(self, query: str, context_data: str, k: int = 4) -> List[Tuple[str, str, float]]:
        """Wrapper for backward compatibility - now uses context-aware retrieval"""
        return self.retrieve_context_aware(query, context_data, k)

    def build_prompt(self, query: str, retrieved: List[Tuple[str, str, float]], context_data: str) -> str:
        """FIXED: Build enhanced prompt with better conversation context"""
        context = "\n\n".join([f"[{cid}] {txt}" for cid, txt, _ in retrieved])
        
        # Add conversation context if available
        conversation_context = ""
        if self.conversation_history and len(self.conversation_history) > 0:
            last_exchange = self.conversation_history[-1]
            last_user_query = last_exchange.get('user', '')
            last_assistant_response = last_exchange.get('assistant', '')
            
            # Only add context if it's meaningful and not too long
            if last_user_query and len(last_user_query) < 200:
                conversation_context = f"""
Previous conversation context:
User previously asked: "{last_user_query}"
My previous response was about: "{last_assistant_response[:150]}{'...' if len(last_assistant_response) > 150 else ''}"
"""
        
        prompt = f"""
Context from documents: {context}

Additional location/user data: {context_data}
{conversation_context}
Current question: {query}

Please answer the current question considering both the document context and any relevant conversation history. If the current question refers to something from our previous conversation (like "this", "that", "how does this happen"), use the conversation context to understand what the user is referring to.
        """
        return prompt

    def initialize_chat_session(self, choice: int):
        """Initialize chat session with system instruction"""
        system_instructions = {
            1: '''You are a useful assistant for farmers. Given the query and context provided, help them with farming advice.
                  The context comes from documents outlining farming practices, with tables in HTML/XLSX format.
                  Use the additional location data to provide more insightful answers.
                  Pay close attention to conversation history to maintain context across related questions.
                  When users ask follow-up questions like "How does this happen?" or "What about this?", refer to the previous conversation to understand what they're asking about.
                  Keep answers simple, short, and focused on practical advice.''',
            2: '''You are a useful assistant for farmers. Given the query and context provided, help them choose appropriate pesticides.
                  The context comes from datasets with recommended pesticides for specific crops and safe usage advice.
                  Use the additional location data to provide more insightful answers.
                  Pay close attention to conversation history to maintain context across related questions.
                  When users ask follow-up questions, refer to the previous conversation to understand the context.
                  Keep answers simple, short, and focused on practical pesticide recommendations.'''
        }
        
        # Create new model instance with system instruction
        model_with_system = genai.GenerativeModel(
            self.google_model,
            system_instruction=system_instructions.get(choice, system_instructions[1])
        )
        
        # Start chat session
        chat_session = model_with_system.start_chat(history=[])
        self.chat_session = chat_session
        return chat_session

    def generate_answer(self, prompt: str, choice: int, original_query: str) -> str:
        """FIXED: Generate answer and store original user query instead of full prompt"""
        # Initialize chat session if not exists
        if self.chat_session is None:
            self.initialize_chat_session(choice)
        
        try:
            # Send message to chat session (automatically maintains context)
            response = self.chat_session.send_message(
                prompt,
                generation_config={
                    "temperature": 0.2,
                    "max_output_tokens": 500,
                }
            )
            
            # FIXED: Store the original user query, not the full prompt
            self.conversation_history.append({
                "user": original_query,  # Store original query for better context retrieval
                "assistant": response.text,
                "choice": choice
            })
            
            # Maintain context window
            if len(self.conversation_history) > self.context_window:
                self.conversation_history = self.conversation_history[-self.context_window:]
                
            print(f"DEBUG: Stored conversation - User: '{original_query}', Assistant preview: '{response.text[:100]}...'")
                
            return response.text
            
        except Exception as e:
            print(f"Error generating response: {e}")
            # Fallback to reinitialize session
            self.initialize_chat_session(choice)
            response = self.chat_session.send_message(prompt)
            
            # Store even fallback responses
            self.conversation_history.append({
                "user": original_query,
                "assistant": response.text,
                "choice": choice
            })
            
            return response.text

    def reset_conversation(self):
        """Reset conversation memory (useful for new farming topics)"""
        self.chat_session = None
        self.conversation_history = []
        print("Conversation memory reset")

    def get_conversation_summary(self) -> str:
        """Get summary of recent conversation for debugging"""
        if not self.conversation_history:
            return "No conversation history"
        
        recent = self.conversation_history[-3:]  # Last 3 exchanges
        summary = "Recent conversation:\n"
        for i, exchange in enumerate(recent, 1):
            user_part = exchange['user'][:100] + "..." if len(exchange['user']) > 100 else exchange['user']
            assistant_part = exchange['assistant'][:100] + "..." if len(exchange['assistant']) > 100 else exchange['assistant']
            summary += f"{i}. User: {user_part}\n"
            summary += f"   Assistant: {assistant_part}\n"
        return summary

    def rag_answer(self, query: str, context_data: str, choice: int) -> Tuple[str, List[Tuple[str, str, float]]]:
        """FIXED: Complete RAG pipeline with proper conversation memory"""
        print(f"Processing query: '{query}' with context: {context_data[:100]}...")
        
        # Use context-aware retrieval that considers conversation history
        retrieved = self.retrieve_context_aware(query, context_data)
        
        # Build enhanced prompt with conversation context
        prompt = self.build_prompt(query, retrieved, context_data)
        
        # Generate answer with conversation memory, passing original query
        answer = self.generate_answer(prompt, choice, original_query=query)
        
        return answer, retrieved