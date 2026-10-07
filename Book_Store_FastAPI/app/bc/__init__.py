"""Microsoft Business Central RAG chatbot.

A second, self-contained chatbot (independent of BookBot) that:

1. pulls records from the Business Central API (:mod:`app.bc.client`),
2. flattens *every* field of each record to text, embeds it with the local
   model, and stores the vectors in Qdrant (:mod:`app.bc.vectorstore`), then
3. answers questions grounded in the most similar records via the switchable
   LLM (:mod:`app.bc.service`).

Everything degrades gracefully: with no BC credentials it ingests bundled
sample data, and if ``qdrant-client`` / a Qdrant server is unavailable the UI
shows a clear message instead of crashing.
"""
