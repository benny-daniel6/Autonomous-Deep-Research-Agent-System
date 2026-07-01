"""
50 Benchmark Queries across 5 categories.
"""

SCIENCE_QUERIES = [
    "How does CRISPR-Cas9 work?",
    "What is the current understanding of dark matter?",
    "Explain the mRNA vaccine mechanism.",
    "What are the latest advancements in solid-state batteries?",
    "How does quantum entanglement work?",
    "What are the long-term health effects of microplastics?",
    "Explain the role of the microbiome in human health.",
    "What is the theory of everything in physics?",
    "How do black holes evaporate via Hawking radiation?",
    "What are the ecological impacts of ocean acidification?",
]

CURRENT_EVENTS_QUERIES = [
    "What are the latest AI regulation frameworks in the EU?",
    "Summarize the recent developments in US-China trade relations.",
    "What is the current status of the Artemis moon mission?",
    "Explain the recent shifts in global supply chains.",
    "What are the major outcomes of the latest COP climate summit?",
    "Summarize the recent geopolitical events in the Middle East.",
    "What are the latest policies on remote work across major tech companies?",
    "How are central banks responding to current inflation rates?",
    "What are the newest trends in renewable energy adoption?",
    "Summarize the recent advancements in commercial spaceflight.",
]

CS_QUERIES = [
    "Explain the attention mechanism in transformers.",
    "What is the difference between TCP and UDP?",
    "How do zero-knowledge proofs work in cryptography?",
    "Explain the Paxos consensus algorithm.",
    "What are the core principles of functional programming?",
    "How does garbage collection work in modern programming languages?",
    "Explain the architecture of a microkernel operating system.",
    "What are the advantages of WebAssembly?",
    "How do diffusion models generate images?",
    "Explain the concept of differential privacy.",
]

HISTORY_QUERIES = [
    "What caused the 2008 financial crisis?",
    "Summarize the events leading to the fall of the Roman Empire.",
    "What was the impact of the printing press on Renaissance Europe?",
    "Explain the causes of the French Revolution.",
    "What were the major consequences of the Industrial Revolution?",
    "Summarize the history of the Silk Road.",
    "What led to the end of the Cold War?",
    "Explain the significance of the Magna Carta.",
    "What were the major factors in the colonization of the Americas?",
    "Summarize the events of the Meiji Restoration in Japan.",
]

AMBIGUOUS_QUERIES = [
    "Is nuclear energy safe?",
    "What is the meaning of life?",
    "Are humans fundamentally good or evil?",
    "Is AI going to destroy humanity?",
    "What is the best economic system?",
    "Does free will exist?",
    "Is universal basic income a good idea?",
    "What is consciousness?",
    "Are we alone in the universe?",
    "What is the future of work?",
]

BENCHMARK_QUERIES = (
    [("Science", q) for q in SCIENCE_QUERIES] +
    [("Current Events", q) for q in CURRENT_EVENTS_QUERIES] +
    [("Computer Science", q) for q in CS_QUERIES] +
    [("History", q) for q in HISTORY_QUERIES] +
    [("Ambiguous", q) for q in AMBIGUOUS_QUERIES]
)
