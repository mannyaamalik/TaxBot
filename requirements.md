# TaxBot – Indian Income Tax & GST Expert Chatbot
## Requirements Document (EARS-Style Acceptance Criteria)

> **EARS notation key**
> - **Ubiquitous:** `The system shall …`
> - **Event-driven:** `When <trigger>, the system shall …`
> - **State-driven:** `While <state>, the system shall …`
> - **Option:** `Where <feature is included>, the system shall …`
> - **Unwanted behaviour:** `If <condition>, then the system shall …`

---

## 1. Scope

TaxBot is a retrieval-augmented generation (RAG) chatbot that answers questions about Indian Income Tax and GST. It is grounded exclusively in a curated document knowledge base. It exposes a FastAPI backend and a browser-based chat UI.

---

## 2. Functional Requirements

### 2.1 Knowledge Base Ingestion

**REQ-KB-01**
The system shall ingest PDF, plain-text, and Markdown documents into ChromaDB by chunking each document into passages of configurable size (default 512 tokens) with configurable overlap (default 64 tokens).

**REQ-KB-02**
When a document is ingested, the system shall store the following metadata with every chunk: source filename, document title, section heading, page number (where available), and ingestion timestamp.

**REQ-KB-03**
When a document with the same filename already exists in the knowledge base, the system shall replace all previously stored chunks for that document with the newly ingested chunks.

**REQ-KB-04**
The system shall embed each chunk using a configurable sentence-transformer model (default: `sentence-transformers/all-MiniLM-L6-v2`) and store the embedding in ChromaDB alongside the chunk text and metadata.

**REQ-KB-05**
Where an OpenAI-compatible embeddings API key is configured, the system shall use the external API for embedding instead of the local sentence-transformer model, without requiring any other code change.

---

### 2.2 Retrieval

**REQ-RET-01**
When a user submits a question, the system shall embed the question using the same model and configuration used during ingestion, then perform a cosine-similarity search against ChromaDB to retrieve the top-k most relevant chunks (default k = 5, configurable).

**REQ-RET-02**
The system shall filter retrieval results to include only chunks with a cosine-similarity score above a configurable threshold (default 0.40). Chunks below the threshold shall be discarded before answer generation.

**REQ-RET-03**
If no chunk meets the similarity threshold, the system shall return a "not found" response (see REQ-ANS-04) without invoking the language model.

---

### 2.3 Answer Generation

**REQ-ANS-01**
When retrieved chunks are available, the system shall construct a prompt that contains: (a) a system instruction restricting the model to answer only from the provided context, (b) the retrieved chunk texts with their source metadata, and (c) the user's question.

**REQ-ANS-02**
The system shall generate answers using a configurable LLM backend (default: a locally running Ollama model; optionally an OpenAI-compatible API endpoint).

**REQ-ANS-03**
Every generated answer shall include a "Sources" section that lists, for each cited chunk: the document title, section heading, and page number (where available).

**REQ-ANS-04**
If the knowledge base contains no passage that answers the question, the system shall respond with a fixed message such as: *"I could not find an answer to this question in my knowledge base. Please consult a qualified tax professional or the official Income Tax / GST portal."* The system shall not speculate or generate an answer from model weights alone.

**REQ-ANS-05**
The system shall not answer questions outside the domains of Indian Income Tax and GST. If a question is outside scope, the system shall respond that it is limited to Indian Income Tax and GST queries.

---

### 2.4 Domain Coverage

The knowledge base shall include, at minimum, documents covering:

**REQ-DOM-01** Income tax slabs for all assessment years present in the knowledge base, including both the old and new tax regimes.

**REQ-DOM-02** Chapter VI-A deductions (80C, 80CCC, 80CCD, 80D, 80DD, 80E, 80G, 80TTA, and others present in the Act).

**REQ-DOM-03** ITR form selection guide (ITR-1 through ITR-7) and filing procedures.

**REQ-DOM-04** GST registration requirements, thresholds, and procedures.

**REQ-DOM-05** GST return filing (GSTR-1, GSTR-3B, GSTR-9, and others in the knowledge base) including due dates.

**REQ-DOM-06** TDS provisions: rates, threshold limits, applicable sections (194A, 194C, 194J, etc.), and certificate procedures.

**REQ-DOM-07** Capital gains: short-term and long-term classification, applicable tax rates, exemption sections (54, 54B, 54EC, 54F), and indexation rules.

---

### 2.5 API (FastAPI Backend)

**REQ-API-01**
The system shall expose a `POST /chat` endpoint that accepts a JSON body `{ "question": string, "session_id": string? }` and returns `{ "answer": string, "sources": Source[], "session_id": string }`.

**REQ-API-02**
The system shall expose a `POST /ingest` endpoint (authenticated) that accepts a multipart file upload and triggers document ingestion, returning a job status object.

**REQ-API-03**
The system shall expose a `GET /health` endpoint that returns the service status and the number of chunks currently stored in ChromaDB.

**REQ-API-04**
When a request to `POST /chat` is missing the `question` field or the field is an empty string, the system shall return HTTP 422 with a descriptive validation error.

**REQ-API-05**
The system shall enforce a rate limit of 30 requests per minute per IP address on the `/chat` endpoint. If the limit is exceeded, the system shall return HTTP 429.

**REQ-API-06**
The system shall maintain per-session conversation history (last N turns, configurable, default 5) and include it in the LLM prompt to support follow-up questions within the same session.

---

### 2.6 Chat UI

**REQ-UI-01**
The system shall provide a single-page web chat interface served by FastAPI (or a standalone HTML file) that allows users to type a question and receive a formatted answer.

**REQ-UI-02**
When the system returns an answer, the UI shall display the answer text followed by a collapsible "Sources" section listing each cited document and section.

**REQ-UI-03**
While the system is generating an answer, the UI shall display a loading indicator and disable the submit button to prevent duplicate submissions.

**REQ-UI-04**
When the system returns a "not found" response, the UI shall render it in a visually distinct style (e.g., amber/warning colour) to distinguish it from a normal answer.

**REQ-UI-05**
The UI shall preserve the full conversation history within a session and display it as a scrollable chat thread.

---

## 3. Non-Functional Requirements

### 3.1 Performance

**REQ-NFP-01**
The system shall return a complete answer within 15 seconds of receiving a question on commodity hardware (8 GB RAM, CPU-only inference).

**REQ-NFP-02**
The retrieval step (embedding + ChromaDB search) shall complete within 2 seconds for a knowledge base of up to 50,000 chunks.

### 3.2 Accuracy & Grounding

**REQ-NFP-03**
The system shall not produce any answer that is not traceable to at least one chunk in the knowledge base. This is enforced architecturally: the LLM prompt shall instruct the model to answer only from the supplied context and to say "I don't know" otherwise.

**REQ-NFP-04**
Every answer shall cite at least one source. If the LLM output does not contain a citation, the backend shall append the retrieved source metadata before returning the response.

### 3.3 Security

**REQ-NFP-05**
The `/ingest` endpoint shall require a bearer token (configurable via environment variable). All other endpoints are unauthenticated.

**REQ-NFP-06**
The system shall not log or persist the full text of user questions beyond the in-memory session store, to protect user privacy.

### 3.4 Configurability

**REQ-NFP-07**
All tuneable parameters (embedding model, LLM endpoint, chunk size, overlap, top-k, similarity threshold, rate limit, session history length) shall be configurable via environment variables or a `.env` file without modifying source code.

### 3.5 Maintainability

**REQ-NFP-08**
The system shall be structured into distinct layers: ingestion, retrieval, generation, API, and UI — each in a separate module or package — so that any single layer can be replaced without touching the others.

---

## 4. Constraints

| Constraint | Detail |
|---|---|
| Language | Python 3.11+ |
| Web framework | FastAPI |
| Vector store | ChromaDB (local, persistent) |
| Default embeddings | `sentence-transformers/all-MiniLM-L6-v2` |
| Default LLM | Ollama (local); OpenAI-compatible API as an option |
| Knowledge base scope | Indian Income Tax Act, GST Act, CBDT/CBIC circulars, official FAQs only |
| Deployment | Single-host, no cloud dependency required |
| Licence | Knowledge base documents must be publicly available government publications |

---

## 5. Out of Scope

- State-level taxes (VAT, stamp duty, profession tax).
- International tax treaties or FEMA.
- Filing actual returns on behalf of the user (no integration with the Income Tax portal or GST portal APIs).
- User authentication beyond the ingest-endpoint bearer token.
- Multi-tenancy or multi-language (Hindi, etc.) in v1.

---

## 6. Glossary

| Term | Definition |
|---|---|
| Chunk | A fixed-size text passage extracted from a source document during ingestion |
| Embedding | A dense vector representation of a text chunk or query |
| RAG | Retrieval-Augmented Generation: retrieve relevant chunks, then generate an answer conditioned on them |
| Top-k | The number of most-similar chunks retrieved per query |
| Session | A stateful conversation identified by a `session_id`; conversation history is kept in memory |
| EARS | Easy Approach to Requirements Syntax — a structured natural-language requirement style |
