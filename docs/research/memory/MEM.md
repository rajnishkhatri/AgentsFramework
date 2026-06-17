link: https://www.linkedin.com/pulse/building-your-first-a-mem-system-connected-memory-smarter-khatri-wjsuc/?trackingId=vgXE55GCQmm9j7osoeHVBA%3D
article: Building Your First A-MEM System - Connected Memory for Smarter Agents

 rajnish khatri
rajnish khatri 

Principal Consultant at Infosys | LLM Evaluation & Multi-Agent Systems Expert


November 18, 2025
Understanding A-MEM Through a Simple Example

Let's build a research assistant that remembers and connects information. Imagine you're helping a student study the solar system - each fact they learn should connect to related facts automatically.

Core Concept: Notes That Link Themselves

Instead of isolated facts, A-MEM creates a web of connected knowledge:

python

# Traditional approach - isolated facts
facts = [
    "Mars is called the red planet",
    "Mars has two moons",
    "Iron oxide causes Mars' red color"
]

# A-MEM approach - connected knowledge
note1 = {
    "content": "Mars is called the red planet",
    "links": [
        {"to": note3, "relation": "explained_by"}
    ]
}
note3 = {
    "content": "Iron oxide causes Mars' red color",
    "links": [
        {"to": note1, "relation": "explains"}
    ]
}
Simple Implementation

Here's a minimal A-MEM implementation to get you started:

python

import hashlib
from typing import List, Dict
import numpy as np
from sentence_transformers import SentenceTransformer

class SimpleAMEM:
    def __init__(self):
        # Use a small, fast embedding model
        self.encoder = SentenceTransformer('all-MiniLM-L6-v2')
        self.notes = {}  # Store notes by ID
        self.graph = {}  # Store connections
        
    def add_note(self, content: str) -> str:
        """Add a note and auto-link to similar notes"""
        
        # Step 1: Create embedding for similarity search
        embedding = self.encoder.encode(content)
        
        # Step 2: Generate unique ID from content
        note_id = hashlib.md5(content.encode()).hexdigest()[:8]
        
        # Step 3: Find similar existing notes
        similar_notes = self._find_similar(embedding)
        
        # Step 4: Store the note
        self.notes[note_id] = {
            'content': content,
            'embedding': embedding,
            'keywords': self._extract_keywords(content)
        }
        
        # Step 5: Create links to similar notes
        self.graph[note_id] = []
        for similar_id, similarity in similar_notes:
            if similarity > 0.7:  # Only strong connections
                self.graph[note_id].append({
                    'to': similar_id,
                    'strength': similarity,
                    'type': 'related'
                })
        
        return note_id
    
    def search_with_links(self, query: str, max_depth: int = 1):
        """Search notes and include linked context"""
        
        # Find directly matching notes
        query_embedding = self.encoder.encode(query)
        direct_matches = self._find_similar(query_embedding)
        
        # Expand to include linked notes
        all_results = set()
        for note_id, score in direct_matches[:3]:
            all_results.add(note_id)
            
            # Add linked notes (depth = 1)
            if note_id in self.graph:
                for link in self.graph[note_id]:
                    all_results.add(link['to'])
        
        # Return note contents
        return [self.notes[nid]['content'] for nid in all_results]
    
    def _find_similar(self, embedding, top_k: int = 5):
        """Find most similar notes by embedding"""
        similarities = []
        
        for note_id, note in self.notes.items():
            # Cosine similarity
            similarity = np.dot(embedding, note['embedding']) / (
                np.linalg.norm(embedding) * np.linalg.norm(note['embedding'])
            )
            similarities.append((note_id, float(similarity)))
        
        return sorted(similarities, key=lambda x: x[1], reverse=True)[:top_k]
    
    def _extract_keywords(self, content: str) -> List[str]:
        """Simple keyword extraction"""
        # In production, use an LLM or NLP library
        words = content.lower().split()
        # Filter common words (simplified)
        stopwords = {'the', 'is', 'at', 'which', 'on', 'a', 'an'}
        return [w for w in words if w not in stopwords][:5]

# Usage example
amem = SimpleAMEM()

# Add related notes about Mars
amem.add_note("Mars is called the red planet due to iron oxide on its surface")
amem.add_note("Mars has two small moons named Phobos and Deimos")
amem.add_note("Iron oxide, also known as rust, gives Mars its reddish appearance")
amem.add_note("The Martian atmosphere is very thin, mostly carbon dioxide")

# Search with automatic link expansion
results = amem.search_with_links("What makes Mars red?")
# Returns the iron oxide notes plus linked Mars facts
Key Design Decisions Explained

Why use embeddings for linking? Embeddings capture semantic meaning, so "red planet" and "reddish appearance" are recognized as related even with different words.

Why hash the content for IDs? This makes notes idempotent - adding the same content twice won't create duplicates. It's like a natural deduplication system.

Why limit link depth? Going beyond 1-2 links adds noise. If Note A links to B, and B links to C, and C links to D, note D is probably not relevant to queries about A.

Practical Tips for Production

Start with simple similarity linking - You don't need complex LLM evaluation initially. Cosine similarity > 0.7 is often good enough.
Add links gradually - Don't recompute all links when adding a note. Just link the new note to existing ones.
Cache aggressively - Store similarity scores, reuse embeddings, and cache search results for common queries.
Monitor link quality - Track which links users actually follow or find useful, and adjust your threshold accordingly.

When to Upgrade from This Simple Version

Start with this simple implementation. Consider upgrading when:

You need typed relationships ("contradicts" vs "supports" vs "elaborates")
Link quality matters more than speed (add LLM validation)
You have >10,000 notes (switch to a proper vector database)
You need persistent storage (add PostgreSQL or Neo4j)

Cost Analysis

For a typical agent with 1,000 notes added per day:

Embedding cost: ~$0.10/day (using OpenAI or free with local models)
Storage: ~$5/month for vector database
Link computation: ~$0.50/day if using LLM validation
Total: ~$20-30/month for a production system

Compare this to sending full conversation history every time: you'd pay 10x more in token costs!

Next Steps

In the next article, we'll explore MemoryBank - how to build agents that remember like humans do, with automatic forgetting of irrelevant information.
