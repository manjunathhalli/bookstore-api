"""AI features package — the FastAPI port of the Laravel AI Integration Guide.

Implements all 10 AI concepts on top of the existing models/database:

  1. Sentiment analysis on reviews      (hook in feedback store)
  2. AI book description generator       (admin)
  3. Review summarization
  4. Natural-language search (intent)
  5. AI chatbot (RAG over the catalogue)
  6. Personalized recommendations
  7. Content moderation                  (hook in feedback store)
  8. Auto-tagging / categorization       (hook in book create/update)
  9. Demand forecasting                  (admin)
 10. Semantic search (embeddings)

The reusable model client lives in :mod:`app.core.ai`; the feature logic lives
in :mod:`app.ai.service`; the HTTP surface lives in ``web.py`` (session UI) and
``api.py`` (JWT REST), matching every other feature package in this project.
"""
