# SWE-599

## Scholar Notification & BOUN Researcher Matching System

This project aims to build an automated recommendation and matching system for academic publications. The system monitors a predefined list of publicators (institutions/publishers). When a new paper is released, it triggers a workflow to find and recommend similar articles and researchers specifically from the Boğaziçi University (BOUN) academic corpus.

### Core Workflow
- Subscription & Trigger: Users maintain a "Followed Publicators" list. The system monitors these sources for new releases.

- Text Representation: New publication metadata (titles/abstracts) are processed into high-dimensional vectors.

- Similarity Search: The system performs a similarity lookup against a local vector database of BOUN researchers and their past publications.

**Output:** A recommendation list linking global new releases to local (BOUN) expertise.

---------

#### Week 1: Performance Evaluation & Embedding Comparison

The immediate goal is to establish a benchmark dataset to evaluate different vectorization methods. Since the project relies on finding "similar" content, selecting the most accurate embedding model is critical.
