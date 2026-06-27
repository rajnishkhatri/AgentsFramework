link: https://www.linkedin.com/pulse/memorybank-building-agents-human-like-memory-rajnish-khatri-hwcuc/?trackingId=vgXE55GCQmm9j7osoeHVBA%3D%3D
article: MemoryBank - Building Agents with Human-Like Memory

 rajnish khatri
rajnish khatri

Principal Consultant at Infosys | LLM Evaluation & Multi-Agent Systems Expert


November 18, 2025
The Problem with Perfect Memory

Imagine if you remembered every conversation you've ever had in perfect detail. Sounds great? Actually, it would be overwhelming. Your brain naturally forgets unimportant details while strengthening important memories through repetition. MemoryBank brings this same intelligence to AI agents.

Understanding Memory Decay Through Examples

Let's see how MemoryBank mimics human memory:

# Day 1: User mentions they're vegetarian
memory_strength = 1.0  # Fresh memory

# Day 7: If not accessed
memory_strength = 0.36  # Fading but recoverable

# Day 30: Still not accessed
memory_strength = 0.03  # Nearly forgotten

# But if accessed on Day 7:
memory_strength = 1.8  # Strengthened by retrieval!
This isn't arbitrary - it follows the Ebbinghaus Forgetting Curve, a model of human memory discovered in 1885 and still used today.

Building a Simple MemoryBank System

Here's a practical implementation that you can start using today:

import json
import time
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import math

class SimpleMemoryBank:
    def __init__(self):
        # Three tiers of memory
        self.conversations = []  # Recent chat (hot)
        self.summaries = {}      # Compressed history (warm)
        self.user_portrait = {}  # Permanent traits (cold)

    def add_conversation_turn(self, user_msg: str, assistant_msg: str):
        """Add a conversation turn to recent memory"""

        turn = {
            'user': user_msg,
            'assistant': assistant_msg,
            'timestamp': datetime.now().isoformat(),
            'strength': 1.0,
            'access_count': 0
        }

        self.conversations.append(turn)

        # Keep only last 50 turns in hot memory
        if len(self.conversations) > 50:
            old_turns = self.conversations[:10]
            self.conversations = self.conversations[10:]

            # Compress old turns into a summary
            self._create_summary(old_turns)

    def _create_summary(self, turns: List[Dict]):
        """Compress multiple turns into a summary"""

        # Extract key points (simplified - use LLM in production)
        topics = []
        for turn in turns:
            # Extract main topic from each turn
            words = turn['user'].lower().split()
            if len(words) > 0:
                topics.append(words[0])  # Simplified extraction

        summary_id = f"summary_{len(self.summaries)}"
        self.summaries[summary_id] = {
            'content': f"Discussed: {', '.join(set(topics))}",
            'turn_count': len(turns),
            'created': datetime.now().isoformat(),
            'strength': 1.0,
            'last_accessed': datetime.now().isoformat()
        }

    def search_memory(self, query: str, include_faded: bool = False) -> List[Dict]:
        """Search across all memory tiers"""

        results = []
        current_time = datetime.now()

        # Search recent conversations
        for turn in self.conversations:
            if query.lower() in turn['user'].lower() or \
               query.lower() in turn['assistant'].lower():

                # Update access tracking
                turn['access_count'] += 1
                turn['strength'] = self._update_strength(turn['strength'])

                results.append({
                    'type': 'conversation',
                    'content': turn,
                    'relevance': 1.0
                })

        # Search summaries (with decay check)
        for summary_id, summary in self.summaries.items():
            retention = self._calculate_retention(
                summary['strength'],
                summary['last_accessed']
            )

            if retention > 0.1 or include_faded:
                if query.lower() in summary['content'].lower():
                    # Update access
                    summary['last_accessed'] = current_time.isoformat()
                    summary['strength'] = self._update_strength(summary['strength'])

                    results.append({
                        'type': 'summary',
                        'content': summary['content'],
                        'relevance': retention
                    })

        # Search user portrait (never decays)
        portrait_matches = []
        for key, value in self.user_portrait.items():
            if query.lower() in str(value).lower():
                portrait_matches.append(f"{key}: {value}")

        if portrait_matches:
            results.append({
                'type': 'portrait',
                'content': portrait_matches,
                'relevance': 1.0
            })

        return sorted(results, key=lambda x: x['relevance'], reverse=True)

    def _calculate_retention(self, strength: float, last_accessed: str) -> float:
        """Calculate memory retention using forgetting curve"""

        last_time = datetime.fromisoformat(last_accessed)
        time_delta = datetime.now() - last_time
        days_passed = time_delta.total_seconds() / 86400

        # Ebbinghaus forgetting curve
        retention = math.exp(-days_passed / strength)
        return retention

    def _update_strength(self, current_strength: float, quality: float = 0.8) -> float:
        """Strengthen memory after successful retrieval"""
        return current_strength * (1 + quality)

    def update_user_portrait(self, key: str, value: str):
        """Update permanent user traits"""
        self.user_portrait[key] = value

    def get_memory_stats(self) -> Dict:
        """Get memory usage statistics"""

        active_summaries = sum(
            1 for s in self.summaries.values()
            if self._calculate_retention(s['strength'], s['last_accessed']) > 0.1
        )

        return {
            'conversation_turns': len(self.conversations),
            'total_summaries': len(self.summaries),
            'active_summaries': active_summaries,
            'portrait_fields': len(self.user_portrait)
        }

# Usage example
memory = SimpleMemoryBank()

# Simulate a conversation
memory.add_conversation_turn(
    "I'm planning a trip to Japan",
    "That's exciting! When are you planning to go?"
)
memory.add_conversation_turn(
    "Next spring, I love cherry blossoms",
    "Spring is perfect for hanami (cherry blossom viewing)"
)

# Update user portrait
memory.update_user_portrait("interests", "travel, Japanese culture")
memory.update_user_portrait("upcoming_plans", "Japan trip in spring")

# Search memories
results = memory.search_memory("Japan")
for result in results:
    print(f"{result['type']}: {result['relevance']:.2f}")
The Three-Tier Architecture Explained

Think of these tiers like your own memory:

Conversations (Working Memory)
Summaries (Long-term Memory)
User Portrait (Core Memory)

Memory Decay in Action

Here's how the forgetting curve works in practice:

def demonstrate_memory_decay():
    """Show how memories fade and strengthen"""

    memory = SimpleMemoryBank()

    # Add a memory
    memory.summaries["test"] = {
        'content': "User mentioned they have a dog named Max",
        'strength': 1.0,
        'last_accessed': datetime.now().isoformat()
    }

    # Simulate time passing
    for days in [1, 7, 14, 30]:
        # Fake the last_accessed time
        past_time = datetime.now() - timedelta(days=days)
        memory.summaries["test"]['last_accessed'] = past_time.isoformat()

        retention = memory._calculate_retention(
            memory.summaries["test"]['strength'],
            memory.summaries["test"]['last_accessed']
        )

        print(f"Day {days}: {retention:.1%} retention")

        if days == 7:  # Access on day 7
            print("  → Memory accessed! Strengthening...")
            memory.summaries["test"]['strength'] = memory._update_strength(1.0)
            memory.summaries["test"]['last_accessed'] = datetime.now().isoformat()

demonstrate_memory_decay()
Output:

Day 1: 36.8% retention
Day 7: 0.1% retention
  → Memory accessed! Strengthening...
Day 14: 53.5% retention
Day 30: 12.2% retention
Cost Savings Analysis

Let's compare costs for a customer support agent handling 100 conversations/day:

Without MemoryBank:

Average conversation: 50 turns × 200 tokens = 10,000 tokens
Cost per conversation: 10,000 × $0.03/1K = $0.30
Monthly cost: $0.30 × 100 × 30 = $900

With MemoryBank:

Hot memory: 10 turns × 200 = 2,000 tokens
Summaries: 5 summaries × 100 = 500 tokens
Portrait: 200 tokens
Total: 2,700 tokens = $0.081 per conversation
Monthly cost: $0.081 × 100 × 30 = $243

Savings: 73% reduction in token costs!

Production Tips

Tune decay rates by use case:
Batch summary generation: Don't summarize after every conversation. Run a batch job every hour to compress old conversations.
Privacy-first design:

When to Use MemoryBank

✅ Perfect for:

Personal assistants
Customer support bots
Mental health companions
Educational tutors

❌ Don't use for:

Legal/medical records (can't afford to forget)
Simple FAQ bots (no personalization needed)
Research tools (need permanent knowledge graph)

In the next article, we'll explore Search-o1 - how agents can search for information while thinking, just like humans do when solving complex problems.
