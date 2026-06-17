link: https://www.linkedin.com/pulse/understanding-memory-systems-llm-agents-practical-rajnish-khatri-d0obc/?trackingId=vgXE55GCQmm9j7osoeHVBA%3D%3D

article: Understanding Memory Systems for LLM Agents - A Practical Introduction

 rajnish khatri
rajnish khatri 

Principal Consultant at Infosys | LLM Evaluation & Multi-Agent Systems Expert


November 18, 2025
Why Your AI Agent Needs Better Memory

Imagine you're building a customer support agent. A user contacts you about an issue they discussed last week, but your agent treats them like a complete stranger. Frustrating, right? This is the memory problem we're solving.

Most LLM applications today either have no memory (each request is isolated) or dump entire conversation histories into the context window (expensive and inefficient). There's a better way - let's explore three production-ready memory patterns that solve real problems.

The Three Memory Patterns You Need to Know

1. A-MEM: When You Need Connected Knowledge

Think of A-MEM like Wikipedia for your agent. Each piece of information becomes a "note" that automatically links to related notes, creating a knowledge graph your agent can traverse.

Perfect for:

Research assistants that need to connect dots across documents
Legal or medical agents exploring relationships between cases
Educational tools where concepts build on each other

How it works in simple terms:

python

# When you add a new note about "flamingos are pink"
new_note = "Flamingos are pink due to their diet"

# A-MEM automatically:
# 1. Finds similar notes (maybe about "bird coloration" or "carotenoids")
# 2. Creates smart links between related notes
# 3. Updates keywords so future searches find connected information
2. MemoryBank: When You Need Human-Like Recall

MemoryBank mimics how humans remember - frequently accessed memories stay fresh, while unused ones fade away. It organizes memories into three tiers like your own brain.

Perfect for:

Personal assistants that remember user preferences
Customer support tracking long-term issues
Wellness apps monitoring patterns over time

How it works in simple terms:

python

# Three-tier storage like human memory:
conversations = "What you just talked about" # Last 50 messages
summaries = "Key points from past chats"     # Compressed history  
user_portrait = "Who this person is"         # Permanent traits

# Memories that aren't used gradually fade:
# Day 1: 100% recall
# Day 7: 36% recall (if not accessed)
# Day 30: <10% recall → archived
3. Search-o1: When You Need To Think and Research

Search-o1 lets your agent pause mid-thought to search for information, then continue reasoning with the new knowledge - like a human researcher checking references while writing.

Perfect for:

Financial analysis requiring current data
Medical diagnosis needing latest research
Technical support checking documentation

How it works in simple terms:

python

# Agent reasoning process:
"To answer why flamingos are pink, I need to know their diet"
# <-- Agent pauses here to search "flamingo diet" -->
# Search returns: "Flamingos eat algae rich in carotenoids"
"Now I can explain: carotenoids from algae turn feathers pink"
Quick Decision Guide

Here's how to choose the right pattern for your use case:

Use Baseline RAG when:

You just need simple document retrieval
No personalization required
Cost is a primary concern

Use MemoryBank when:

You need to remember user preferences
Long conversations matter but old details can fade
You want automatic memory management

Use A-MEM when:

Information needs to be interconnected
Users explore related topics
You're building a knowledge discovery tool

Use Search-o1 when:

Accuracy is critical
You need current information during reasoning
Multi-step research is required

What's Next?

In the following articles, we'll dive into implementing each pattern with practical code examples. You don't need to implement all three - pick the one that fits your use case and start there.