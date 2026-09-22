import os, re, json, math

STOPWORDS = {
    'i', 'me', 'my', 'myself', 'we', 'our', 'ours', 'ourselves', 'you', "you're", "you've", "you'll", "you'd",
    'your', 'yours', 'yourself', 'yourselves', 'he', 'him', 'his', 'himself', 'she', "she's", 'her', 'hers',
    'herself', 'it', "it's", 'its', 'itself', 'they', 'them', 'their', 'theirs', 'themselves', 'what', 'which',
    'who', 'whom', 'this', 'that', "that'll", 'these', 'those', 'am', 'is', 'are', 'was', 'were', 'be', 'been',
    'being', 'have', 'has', 'had', 'having', 'do', 'does', 'did', 'doing', 'a', 'an', 'the', 'and', 'but', 'if',
    'or', 'because', 'as', 'until', 'while', 'of', 'at', 'by', 'for', 'with', 'about', 'against', 'between',
    'into', 'through', 'during', 'before', 'after', 'above', 'below', 'to', 'from', 'up', 'down', 'in', 'out',
    'on', 'off', 'over', 'under', 'again', 'further', 'then', 'once', 'here', 'there', 'when', 'where', 'why',
    'how', 'all', 'any', 'both', 'each', 'few', 'more', 'most', 'other', 'some', 'such', 'no', 'nor', 'not',
    'only', 'own', 'same', 'so', 'than', 'too', 'very', 's', 't', 'can', 'will', 'just', 'don', "don't", 'should',
    "should've", 'now', 'd', 'll', 'm', 'o', 're', 've', 'y', 'ain', 'aren', "aren't", 'couldn', "couldn't",
    'didn', "didn't", 'doesn', "doesn't", 'hadn', "hadn't", 'hasn', "hasn't", 'haven', "haven't", 'isn', "isn't",
    'ma', 'mightn', "mightn't", 'mustn', "mustn't", 'needn', "needn't", 'shan', "shan't", 'shouldn', "shouldn't",
    'wasn', "wasn't", 'weren', "weren't", 'won', "won't", 'wouldn', "wouldn't"
}

SYNONYM_MAP = {
    'dyspnea': 'breath',
    'breathless': 'breath',
    'pharyngitis': 'throat',
    'otalgia': 'ear',
    'otitis': 'ear',
    'angina': 'chest',
    'precordial': 'chest',
    'rhinitis': 'nasal',
    'sinusitis': 'sinus',
    'cephalea': 'headache'
}

def tokenize(text):
    text = text.lower()
    words = re.findall(r'\b\w+\b', text)
    tokens = []
    for w in words:
        if w not in STOPWORDS and not w.isdigit():
            tokens.append(w)
            if w in SYNONYM_MAP:
                tokens.append(SYNONYM_MAP[w])
    return tokens

class SimpleRAG:
    def __init__(self, doc_path=None, chunk_size=60, chunk_overlap=20):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.chunks = []
        self.vocab = set()
        self.df = {}
        self.idf = {}
        self.chunk_vectors = []
        
        if doc_path:
            self.load_documents(doc_path)

    def load_documents(self, doc_path):
        if not os.path.exists(doc_path):
            raise FileNotFoundError(f"Clinical database not found at {doc_path}")
            
        with open(doc_path, 'r') as f:
            docs = json.load(f)
            
        self.chunks = []
        for doc in docs:
            words = doc["text"].split()
            if len(words) <= self.chunk_size:
                self.chunks.append({
                    "doc_id": doc["id"],
                    "category": doc["category"],
                    "title": doc["title"],
                    "text": doc["text"]
                })
            else:
                step = self.chunk_size - self.chunk_overlap
                for start in range(0, len(words), step):
                    chunk_words = words[start:start + self.chunk_size]
                    if not chunk_words:
                        break
                    chunk_text = " ".join(chunk_words)
                    self.chunks.append({
                        "doc_id": doc["id"],
                        "category": doc["category"],
                        "title": doc["title"],
                        "text": chunk_text
                    })
                    if start + self.chunk_size >= len(words):
                        break
                        
        self._build_index()

    def _build_index(self):
        self.df = {}
        self.vocab = set()
        tokenized_chunks = []
        
        for chunk in self.chunks:
            tokens = tokenize(chunk["text"])
            tokenized_chunks.append(tokens)
            unique_tokens = set(tokens)
            self.vocab.update(unique_tokens)
            for t in unique_tokens:
                self.df[t] = self.df.get(t, 0) + 1
                
        num_chunks = len(self.chunks)
        for t in self.vocab:
            self.idf[t] = math.log((1 + num_chunks) / (1 + self.df[t])) + 1
            
        self.chunk_vectors = []
        for tokens in tokenized_chunks:
            tf = {}
            for t in tokens:
                tf[t] = tf.get(t, 0) + 1
            
            vector = {}
            length_sq = 0.0
            for t, count in tf.items():
                val = count * self.idf.get(t, 0.0)
                vector[t] = val
                length_sq += val * val
            
            vector["__len__"] = math.sqrt(length_sq)
            self.chunk_vectors.append(vector)

    def retrieve(self, query, top_k=3):
        if not self.chunks:
            return []
            
        query_tokens = tokenize(query)
        if not query_tokens:
            return []
            
        q_tf = {}
        for t in query_tokens:
            q_tf[t] = q_tf.get(t, 0) + 1
            
        q_vector = {}
        q_len_sq = 0.0
        for t, count in q_tf.items():
            val = count * self.idf.get(t, 0.0)
            q_vector[t] = val
            q_len_sq += val * val
        q_len = math.sqrt(q_len_sq)
        
        if q_len == 0:
            return []
            
        scores = []
        for idx, c_vector in enumerate(self.chunk_vectors):
            dot_product = 0.0
            for t, q_val in q_vector.items():
                if t in c_vector:
                    dot_product += q_val * c_vector[t]
                    
            c_len = c_vector["__len__"]
            if c_len == 0:
                similarity = 0.0
            else:
                similarity = dot_product / (q_len * c_len)
                
            scores.append((similarity, idx))
            
        scores.sort(key=lambda x: x[0], reverse=True)
        
        seen_docs = set()
        results = []
        for score, idx in scores:
            if score <= 0.0:
                continue
            chunk = self.chunks[idx]
            doc_id = chunk["doc_id"]
            if doc_id not in seen_docs:
                seen_docs.add(doc_id)
                results.append({
                    "doc_id": doc_id,
                    "category": chunk["category"],
                    "title": chunk["title"],
                    "text": chunk["text"],
                    "score": round(score, 4)
                })
                if len(results) >= top_k:
                    break
                    
        return results

_rag_instance = None

def get_rag():
    global _rag_instance
    if _rag_instance is None:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        doc_path = os.path.join(base_dir, "data", "clinical_docs.json")
        _rag_instance = SimpleRAG(doc_path)
    return _rag_instance
