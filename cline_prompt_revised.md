### **Task: Full Architectural Rebuild of a Systems Engineering Chatbot**

**High-Level Objective:**

Perform a full architectural rebuild of the existing `Systems_Engineering_Chatbot` project. The new architecture should create a sophisticated chatbot that leverages the Gemini API for advanced language understanding, a Neo4j Aura graph database for structured systems data, and knowledge extracted from a scientific paper to provide mathematically informed responses to systems engineering queries.

**Core Components & Data Sources:**

1.  **Gemini API Integration:**
    *   The primary language model for the chatbot will be Google's Gemini.
    *   You will need to integrate the Gemini API for processing user prompts, generating responses, and synthesizing information.
    *   Assume the user will provide the `GEMINI_API_KEY` in an environment variable.

2.  **Neo4j Aura Graph Database Integration:**
    *   The chatbot must connect to and query a specific Neo4j Aura database to retrieve graph-based systems data.
    *   Use the following credentials to establish the connection. These should be stored securely in a `.env` file.
        *   **URI:** `neo4j+s://eacf92e2.databases.neo4j.io`
        *   **Username:** `neo4j`
        *   **Password:** `lT1xHQLBH31FHzumUjOy2cvFcdoB6kVPXrhhegnZ9J6`
        *   **Database:** `neo4j`
    *   The data retrieved from this database will form a core component of the chatbot's knowledge base.

3.  **PDF Document Processing:**
    *   The chatbot must read and process the provided PDF document: `Wach_PF_D_2023 (1).pdf`.
    *   Utilize Natural Language Processing (NLP) techniques to identify and extract relevant table data from this paper. This data is crucial for informing the chatbot's responses.

**Functional Requirements:**

1.  **Query Handling:** The chatbot must be able to answer key systems engineering prompts, including (but not limited to):
    *   "What are the system requirements for [System Name]?"
    *   "Describe the System Descriptions (SDs) for [System Component]."
    *   "List the Verification Requirements (VRs) associated with [System]."
    *   "Detail the Verification Modules (VMs) for [Requirement]."

2.  **Response Generation:** This is the most critical requirement. Responses should **not** be simple text. Each response must be formulated with **algebraic structures** that are mathematically derived from a synthesis of the three data sources:
    *   The theoretical framework and tables from the **Wach paper**.
    *   The specific graph data points from the **Neo4j database**.
    *   The contextual understanding and reasoning capabilities of the **Gemini API**.

3.  **Training Data:** The data extracted from the Neo4j database and the Wach paper tables should be treated as the foundational training and reference data for the chatbot's response generation model.

**Architectural Requirements:**

1.  **Full Architectural Rebuild:** Analyze the existing codebase in the `Systems_Engineering_Chatbot/` directory and refactor it completely to meet these new, advanced requirements. This includes restructuring the application logic, data processing pipelines, and API integrations. The existing UI and context management system should be preserved.

**Suggested Implementation Plan:**

1.  **Environment Setup:** Securely configure the Neo4j and Gemini API credentials in the `.env` file.
2.  **PDF Data Extractor:** Create a new Python module (`pdf_processor.py`) that uses a library like `PyMuPDF` or `pdfplumber` to parse `Wach_PF_D_2023 (1).pdf` and extract the relevant tables into a structured format (e.g., pandas DataFrames).
3.  **Neo4j Integration:** Refactor `src/neo4j_integration.py` to connect to the specified Aura database and include functions for querying system requirements, SDs, VRs, and VMs.
4.  **Gemini API Integration:** Refactor `src/api_integration.py` to use the Gemini API. Create helper functions for sending prompts and processing the model's output.
5.  **Core Logic - Algebraic Synthesis:** Create a new core module (e.g., `src/synthesis_engine.py`). This will be the brain of the application. It should:
    *   Take a user prompt as input.
    *   Query the Neo4j database and the extracted PDF data.
    *   Feed this information, along with the user prompt, to the Gemini API.
    *   Contain the logic to construct the final algebraic response based on the inputs from all three sources.
6.  **Application Integration:**
    *   Rebuild the Flask application (`src/app.py`) to orchestrate the new workflow, while ensuring the existing UI and context management systems remain functional.
