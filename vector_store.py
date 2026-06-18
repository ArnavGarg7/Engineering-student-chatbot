import os
import logging
from pathlib import Path

# Attempt to import chromadb gracefully
try:
    import chromadb
    from chromadb.utils.embedding_functions import DefaultEmbeddingFunction
    CHROMADB_AVAILABLE = True
except ImportError as e:
    CHROMADB_AVAILABLE = False
    chromadb_import_error = str(e)


BASE_DIR = Path(__file__).resolve().parent
CHROMA_DB_PATH = BASE_DIR / "chroma_db"

logger = logging.getLogger("vector_store")

class RAGStore:
    def __init__(self):
        self.client = None
        self.schema_coll = None
        self.rules_coll = None
        self.sql_coll = None
        self.ready = False
        
        # Simple memory cache for identical queries
        self._cache_schema = {}
        self._cache_rules = {}
        self._cache_sql = {}
        
    def initialize(self):
        if self.ready:
            return
            
        if not CHROMADB_AVAILABLE:
            logger.error("RAGStore: chromadb module is not available. Error: %s", chromadb_import_error)
            return
            
        if not CHROMA_DB_PATH.exists():
            logger.warning("RAGStore: chroma_db directory not found. Please run build_vector_index.py")
            return
            
        try:
            self.client = chromadb.PersistentClient(path=str(CHROMA_DB_PATH))
            ef = DefaultEmbeddingFunction()
            
            try:
                self.schema_coll = self.client.get_collection(name="schema_collection", embedding_function=ef)
            except ValueError:
                self.schema_coll = None
                
            self.rules_coll = self.client.get_collection(name="business_rules_collection", embedding_function=ef)
            self.sql_coll = self.client.get_collection(name="sql_examples_collection", embedding_function=ef)
            
            self.ready = True
            logger.info("RAGStore: Initialized successfully.")
        except Exception as e:
            logger.error("RAGStore: Failed to initialize: %s", e)

    def _retrieve(self, collection_name: str, query: str, top_k: int, cache_dict: dict) -> tuple[list[str], list[str]]:
        if not self.ready:
            self.initialize()
            if not self.ready:
                return [], []
                
        collection = getattr(self, collection_name)
        if not collection:
            return [], []
                
        # Check cache
        cache_key = f"{query}_{top_k}"
        if cache_key in cache_dict:
            return cache_dict[cache_key]
            
        try:
            results = collection.query(
                query_texts=[query],
                n_results=top_k
            )
            
            if not results['documents'] or not results['documents'][0]:
                cache_dict[cache_key] = ([], [])
                return [], []
                
            docs = results['documents'][0]
            ids = results['ids'][0] if 'ids' in results and results['ids'] else []
            cache_dict[cache_key] = (docs, ids)
            return docs, ids
            
        except Exception as e:
            logger.error(f"RAGStore retrieve error: {e}")
            return [], []

    def retrieve_schema(self, query: str, top_k: int = 3) -> tuple[list[str], list[str]]:
        return self._retrieve('schema_coll', query, top_k, self._cache_schema)
        
    def retrieve_business_rules(self, query: str, top_k: int = 2) -> tuple[list[str], list[str]]:
        return self._retrieve('rules_coll', query, top_k, self._cache_rules)
        
    def retrieve_sql_examples(self, query: str, top_k: int = 4) -> tuple[list[str], list[str]]:
        return self._retrieve('sql_coll', query, top_k, self._cache_sql)

store = RAGStore()
