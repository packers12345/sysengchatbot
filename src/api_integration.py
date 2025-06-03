import pypyodbc as odbc  # pip install pypyodbc
import openai
import spacy
import re
from typing import Dict, List, Any
import PyPDF2  # Import the PyPDF2 library
from io import BytesIO
import base64
import os
import requests  # Added for image downloading

# For Graphormer integration and visualization
import networkx as nx
from pyvis.network import Network
import json
from pathlib import Path
import graphviz  # Add this import at the top with other imports

from dotenv import load_dotenv, find_dotenv

# Explicitly load .env from the directory containing this script
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), ".env"))


# Load spaCy NLP model
nlp = spacy.load("en_core_web_sm")

def initialize_api(api_key: str = None) -> bool:
    """Initialize the OpenAI API using the provided API key or from environment variable OPENAI_API_KEY."""
    if api_key is None:
        api_key = os.environ.get("API_KEY")
    if not api_key:
        print("No API key provided.")
        return False
    try:
        openai.api_key = api_key
        print("API initialized with key from environment variable." if api_key == os.environ.get("API_KEY") else f"API initialized with key: {api_key}")
        return True
    except Exception as e:
        print(f"Error initializing API: {e}")
        return False

def connect_to_db():
    """
    Establish an ODBC connection to Azure SQL Database using environment variables.
    Expects:
        - DB_SERVER:      e.g. "humedbserver.database.windows.net"
        - DB_NAME:        e.g. "HumeDBNew"
        - DB_USER:        e.g. "HumeDBNew@humedbserver"
        - DB_PASSWORD:    your strong password
    Returns an open connection or None on failure.
    """
    # Read from environment variables (no defaults hard-coded)
    server   = os.environ.get("DB_SERVER")
    database = os.environ.get("DB_NAME")
    username = os.environ.get("DB_USER")
    password = os.environ.get("DB_PASSWORD")

    # Basic sanity check
    if not all([server, database, username, password]):
        print("Error: One or more required environment variables (DB_SERVER, DB_NAME, DB_USER, DB_PASSWORD) are missing.")
        return None

    # Build the ODBC connection string
    connection_string = (
        "Driver={ODBC Driver 18 for SQL Server};"
        f"Server=tcp:{server},1433;"
        f"Database={database};"
        f"Uid={username};"
        f"Pwd={password};"
        "Encrypt=yes;"
        "TrustServerCertificate=no;"
        "Connection Timeout=30;"
    )

    # Attempt to connect
    try:
        conn = odbc.connect(connection_string)
        return conn
    except Exception as e:
        print(f"Database connection error: {e}")
        return None

def list_all_tables() -> List[str]:
    """Retrieve a list of all tables in the 'dbo' schema."""
    conn = connect_to_db()
    if not conn:
        return []
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA = 'dbo';")
        tables = [row[0] for row in cursor.fetchall()]
        conn.close()
        if tables:
            print(f"Tables have been retrieved successfully: {tables}")
        else:
            print("No tables found in the 'dbo' schema.")
        return tables
    except Exception as e:
        print(f"Error fetching table list: {e}")
        return []

def fetch_table_structure() -> Dict[str, Dict[str, str]]:
    """Retrieve column details for all tables in the database."""
    conn = connect_to_db()
    if not conn:
        return {}
    table_structure = {}
    try:
        cursor = conn.cursor()
        tables = list_all_tables()
        for table in tables:
            cursor.execute(f"""
                SELECT COLUMN_NAME, DATA_TYPE
                FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_NAME = '{table}';
            """)
            columns = cursor.fetchall()
            table_structure[table] = {col[0]: col[1] for col in columns}
        conn.close()
        return table_structure
    except Exception as e:
        print(f"Error fetching table structures: {e}")
        return {}

def fetch_specific_table(table_name: str, limit: int = 5) -> List[Any]:
    """
    Fetch up to `limit` rows from the given table_name.
    Returns a list of tuples (one tuple per row).
    """
    conn = connect_to_db()
    if not conn:
        return []
    try:
        cursor = conn.cursor()
        if not re.match(r'^\w+$', table_name):
            raise ValueError("Invalid table name format.")
        query = f"SELECT TOP {limit} * FROM {table_name};"
        cursor.execute(query)
        rows = cursor.fetchall()
        conn.close()
        return rows
    except Exception as e:
        print(f"Error fetching data from table '{table_name}': {e}")
        return []

def detect_table_name(user_text: str) -> str:
    """
    Use regex to detect a table name mentioned in user_text.
    Example: if user_text contains 'table system_requirements', returns 'system_requirements'.
    """
    pattern = re.compile(r'\btable\s+([a-zA-Z0-9_]+)', re.IGNORECASE)
    match = pattern.search(user_text)
    if match:
        return match.group(1)
    return ""

def enhance_user_requirements(user_text: str) -> str:
    """
    Process and enhance the free-form user input using NLP.
    Extracts key phrases and entities to form a more precise prompt.
    """
    doc = nlp(user_text)
    key_phrases = set(chunk.text.strip() for chunk in doc.noun_chunks)
    key_phrases.update(ent.text.strip() for ent in doc.ents)
    enhanced_text = user_text.strip()
    if key_phrases:
        enhanced_text += "\nKey concepts: " + ", ".join(key_phrases)
    if len(user_text.split()) < 20:
        enhanced_text += "\n[Note: The input is brief; more detail may yield a richer design.]"
    print("Enhanced User Requirements:")
    print(enhanced_text)
    return enhanced_text

def extract_text_from_pdf(pdf_file: BytesIO) -> str:
    """Extract text from the given PDF file."""
    text = ""
    try:
        pdf_reader = PyPDF2.PdfReader(pdf_file)
        for page in pdf_reader.pages:
            text += page.extract_text()
    except Exception as e:
        print(f"Error reading PDF: {e}")
    return text

def generate_system_designs(user_requirements: str, examples: Any = None, pdf_data: BytesIO = None) -> str:
    """Generate a concise system design document (500 words) incorporating provided data."""
    if not isinstance(examples, dict):
        print("Warning: 'examples' parameter is not a dictionary. Using default examples.")
        examples = {
            "example_reqs": "Example system requirements: [Default structured requirements].",
            "example_designs": "Example system designs: [Detailed design example]."
        }
    try:
        processed_requirements = enhance_user_requirements(user_requirements)
        table_structure = fetch_table_structure()
        referenced_table = detect_table_name(user_requirements)
        table_data_string = ""
        if referenced_table:
            rows = fetch_specific_table(referenced_table, limit=5)
            if rows:
                table_data_string = f"Sample rows from '{referenced_table}':\n"
                for i, row in enumerate(rows, start=1):
                    table_data_string += f"Row {i}: {row}\n"
            else:
                table_data_string = f"No data found for table '{referenced_table}'.\n"
        if pdf_data:
            pdf_text = extract_text_from_pdf(pdf_data)
            processed_requirements += f"\nPDF data: {pdf_text}"
        else:
            print("No PDF data provided; skipping PDF extraction.")
        query_text = f"""
User Requirements (enhanced):
{processed_requirements}

Reference Requirements:
{examples.get("example_reqs", "")}

Reference Designs:
{examples.get("example_designs", "")}

Database Structure:
{table_structure}

{table_data_string}

Generate a concise system design document (500 words) that includes:
1. A mathematical description of the system requirements (use LaTeX for any math equations, e.g. $$E=mc^2$$, and include tables as regular HTML).
2. Acceptable system designs with formal proofs (using key properties and homomorphism).
3. Unacceptable designs with proofs outlining discrepancies.
4. Recommendations for improvement.
5. A formal proof of homomorphism demonstrating equivalence between requirements and designs.
6. Rely on the prompts that the user sends to create the response, not the examples e.g. flashlight.
 
IMPORTANT:
- DO NOT use any generic or fallback examples like the flashlight unless specified, look at the USERS INPUT ONLY and reference it with SQL/PDF data
- Clearly label each section with appropriate headings.
- Ensure any defined mathematical expressions are formatted in LaTeX.
- Keep the response self-contained and data-driven.
        """
        print("Final Query Text for System Designs:")
        print(query_text)
        client = openai.OpenAI(api_key=openai.api_key)
        response = client.chat.completions.create(
            model="gpt-4.1-nano",
            messages=[{"role": "user", "content": query_text}],
            max_tokens=1500,
            temperature=0.7
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"Error in generating system designs: {str(e)}"

def create_verification_requirements_models(system_requirements: str, examples: Any = None, pdf_data: BytesIO = None) -> str:
    """Generate a concise verification requirements document (500 words) integrating provided data."""
    if not isinstance(examples, dict):
        print("Warning: 'examples' parameter is not a dictionary. Using default examples.")
        examples = {
            "example_system_reqs": "Example system requirements: [Structured requirements].",
            "example_verif_reqs": {"verification": {"details": [{"example": "verification structure"}]}},
            "example_designs": {"design": {"details": [{"example": "system design structure"}]}}
        }
    try:
        processed_requirements = enhance_user_requirements(system_requirements)
        if pdf_data:
            pdf_text = extract_text_from_pdf(pdf_data)
            processed_requirements += f"\nPDF data: {pdf_text}"
        else:
            print("No PDF data provided; skipping PDF extraction.")
        query_text = f"""
Enhanced System Requirements:
{processed_requirements}

Reference Requirements:
{examples.get("example_system_reqs", "")}

Reference Verification Examples:
{examples.get("example_verif_reqs", "")}

Reference Designs:
{examples.get("example_designs", "")}

Generate a concise verification requirements document (500 words) that includes:
1. Detailed verification problem spaces with proofs of morphism to the system requirements.
2. Verification models with proofs indicating adherence to these problem spaces.
3. A formal yes/no proof of homomorphism demonstrating equivalence between system designs and verification requirements.

IMPORTANT:
- DO NOT use any generic or fallback examples like the flashlight unless specified, look at the USERS INPUT ONLY and reference it with SQL/PDF data
- Clearly label every section (for example, 'Verification Problem Spaces', 'Verification Models', etc.).
- Format any defined mathematical expressions correctly.
- Keep the response self-contained and data-driven.
        """
        print("Final Query Text for Verification Requirements:")
        print(query_text)
        client = openai.OpenAI(api_key=openai.api_key)
        response = client.chat.completions.create(
            model="gpt-4.1-nano",
            messages=[{"role": "user", "content": query_text}],
            max_tokens=1500,
            temperature=0.7
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"Error in generating verification requirements and models: {str(e)}"

def get_traceability(system_requirements: str, example_system_requirements: str,
                      example_system_designs: Dict[str, Dict[str, List[Dict[str, str]]]]) -> str:
    """Generate traceability and proof based on the given system requirements and example system designs in 500 words."""
    try:
        query_text = f"""
Generate traceability and proof based on the given system requirements. The provided example system designs and their corresponding system requirements are for structure reference only. Do not use the example content directly.

Example System Requirements (for structure reference only):
{example_system_requirements}

Example System Designs (for structure reference only):
{example_system_designs}

System Requirements: {system_requirements}

Please provide your answer in clearly labeled sections. Include:
1. A traceability matrix formatted as a clean HTML table (with bold headers and no extraneous rows).
2. A short, spaced proof of traceability explanation that follows the table.

IMPORTANT:
- DO NOT use any generic or fallback examples like the flashlight unless specified, look at the USERS INPUT ONLY and reference it with SQL/PDF data
- Format any defined mathematical expressions in LaTeX.
- Clearly label each section with headers (e.g., "Traceability Matrix", "Proof of Traceability").
- Ensure the table is neatly formatted, accounting for missing data.
        """
        client = openai.OpenAI(api_key=openai.api_key)
        response = client.chat.completions.create(
            model="gpt-4.1-nano",
            messages=[{"role": "user", "content": query_text}],
            max_tokens=1500,
            temperature=0.7
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"Error in generating traceability: {str(e)}"

def get_verification_conditions(system_requirements: str, example_system_requirements: str,
                                example_verification_requirements: Dict[str, Dict[str, List[Dict[str, str]]]],
                                example_system_designs: Dict[str, Dict[str, List[Dict[str, str]]]]) -> str:
    """Generate verification conditions based on the given system requirements and example verification requirements in 500 words."""
    try:
        query_text = f"""
Generate verification conditions based on the given system requirements. The provided example system requirements, verification requirements, and system designs are for structure reference only. Do not use the example content directly.

Example System Requirements (for structure reference only):
{example_system_requirements}

Example Verification Requirements (for structure reference only):
{example_verification_requirements}

Example System Designs (for structure reference only):
{example_system_designs}

System Requirements: {system_requirements}

Please provide your answer in clearly labeled sections. Include:
1. A description of the type of homomorphism (e.g., Homomorphism, Isomorphism, Identity isomorphism, Parameter morphism) along with a clear explanation.
2. A discussion of the verification requirement problem space with clear definitions.
3. A proof of the type of homomorphism and the verification requirement problem space.

IMPORTANT:
- DO NOT use any generic or fallback examples like the flashlight unless specified, look at the USERS INPUT ONLY and reference it with SQL/PDF data.
- Format any defined mathematical expressions in LaTeX if needed.
- Clearly label each section with headers.
- Keep the response self-contained and data-driven.
        """
        client = openai.OpenAI(api_key=openai.api_key)
        response = client.chat.completions.create(
            model="gpt-4.1-nano",
            messages=[{"role": "user", "content": query_text}],
            max_tokens=1500,
            temperature=0.7
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"Error in generating verification conditions: {str(e)}"

import torch
from diffusers import StableDiffusion3Pipeline

import itertools

def extract_important_phrases(text: str) -> list:
    """
    Extracts important phrases from the requirements text and user input:
    - Phrases containing numbers, units, or mathematical/engineering keywords.
    - Named entities of type QUANTITY, CARDINAL, PERCENT, TIME, DATE, or ORDINAL.
    - Phrases mentioning models, equations, constraints, state machines, etc.
    """
    doc = nlp(text)
    keywords = [
        "constraint", "model", "equation", "state machine", "differential equation",
        "threshold", "limit", "performance", "acceleration", "speed", "force", "balance",
        "representation", "convert", "compare", "problem space"
    ]
    # Lowercase keywords for matching
    keywords = [k.lower() for k in keywords]

    # 1. Extract entities with numbers/quantities
    important_phrases = set()
    for ent in doc.ents:
        if ent.label_ in {"QUANTITY", "CARDINAL", "PERCENT", "TIME", "DATE", "ORDINAL"}:
            important_phrases.add(ent.text.strip())
        # Also add entities with numbers/units
        if re.search(r"\d", ent.text) or re.search(r"\b(sec|second|mph|km/h|ms|g|kg|Hz|%)\b", ent.text, re.I):
            important_phrases.add(ent.text.strip())

    # 2. Extract noun chunks or sentences with keywords or numbers
    for chunk in doc.noun_chunks:
        chunk_text = chunk.text.strip()
        if any(k in chunk_text.lower() for k in keywords):
            important_phrases.add(chunk_text)
        elif re.search(r"\d", chunk_text):
            important_phrases.add(chunk_text)
        elif re.search(r"\b(sec|second|mph|km/h|ms|g|kg|Hz|%)\b", chunk_text, re.I):
            important_phrases.add(chunk_text)

    # 3. Extract sentences with keywords or numbers
    for sent in doc.sents:
        sent_text = sent.text.strip()
        if any(k in sent_text.lower() for k in keywords):
            important_phrases.add(sent_text)
        elif re.search(r"\d", sent_text):
            important_phrases.add(sent_text)
        elif re.search(r"\b(sec|second|mph|km/h|ms|g|kg|Hz|%)\b", sent_text, re.I):
            important_phrases.add(sent_text)

    # 4. Remove trivial/short/generic phrases
    filtered = set()
    for phrase in important_phrases:
        if len(phrase) < 4:
            continue
        if phrase.lower() in {"i", "am", "a", "the", "it", "these", "this", "that"}:
            continue
        filtered.add(phrase)

    # 5. Sort by appearance in text
    def phrase_index(phrase):
        try:
            return text.index(phrase)
        except ValueError:
            return 1e9
    sorted_phrases = sorted(filtered, key=phrase_index)
    return sorted_phrases

def generate_network_visualization(graph_data, pdf_data=None):
    """
    Generates a SysML-inspired diagram using Graphviz.
    The user requirements are parsed for key concepts, which are visualized as nodes.
    Returns a raw SVG string from the users input.
    """
    # Extract user requirements text
    user_requirements = ""
    if "user_requirements" in graph_data and graph_data["user_requirements"]:
        user_requirements = graph_data["user_requirements"]
    elif pdf_data:
        user_requirements = extract_text_from_pdf(pdf_data)[:500]
    else:
        user_requirements = "No requirements provided."

    # Use improved phrase extraction
    key_phrases = extract_important_phrases(user_requirements)
    if not key_phrases:
        key_phrases = ["No key requirements found."]

    # Create a Graphviz Digraph
    dot = graphviz.Digraph(comment="SysML-inspired System Requirement Diagram", format="svg")
    dot.attr(rankdir="LR", size="8,5")
    dot.node("REQ", "System Requirement", shape="box", style="filled", fillcolor="#b3c6ff")

    # Add key phrase nodes and connect to central requirement
    for idx, phrase in enumerate(key_phrases):
        node_id = f"KP{idx}"
        dot.node(node_id, phrase, shape="ellipse", style="filled", fillcolor="#e6ffe6")
        dot.edge("REQ", node_id)

    # Optionally, add PDF context as a note node
    if pdf_data:
        pdf_text = extract_text_from_pdf(pdf_data)
        if pdf_text:
            dot.node("PDF", "PDF Context", shape="note", style="filled", fillcolor="#fff2cc")
            dot.edge("REQ", "PDF", style="dashed")

    try:
        svg_bytes = dot.pipe(format="svg")
        svg_str = svg_bytes.decode("utf-8")
        return svg_str
    except Exception as e:
        print(f"Error in Graphviz visualization: {e}")
        return '<svg xmlns="http://www.w3.org/2000/svg" width="400" height="60"><text x="10" y="35" fill="red">Graphviz visualization unavailable (backend error)</text></svg>'

from typing import Optional

def load_pdf_from_env() -> 'Optional[BytesIO]':
    """
    Loads PDF data from PDF_PATH (URL or file path) environment variable.
    Returns a BytesIO object or None.
    """
    pdf_path = os.environ.get("PDF_PATH")
    if pdf_path:
        if pdf_path.startswith("http://") or pdf_path.startswith("https://"):
            # Download PDF from Azure Blob Storage URL
            try:
                response = requests.get(pdf_path)
                response.raise_for_status()
                return BytesIO(response.content)
            except Exception as e:
                print(f"Error downloading PDF from URL '{pdf_path}': {e}")
                return None
        else:
            # Load PDF from local file path
            try:
                with open(pdf_path, "rb") as f:
                    return BytesIO(f.read())
            except Exception as e:
                print(f"Error loading PDF from '{pdf_path}': {e}")
                return None
    else:
        print("Error: PDF_PATH environment variable is not set.")
        return None

if __name__ == "__main__":
    # 1) API init
    if not initialize_api():
        print("Failed to initialize API. Exiting.")
        exit(1)

    # 2) DB connectivity tests …
    tables = list_all_tables()
    print(f"Tables returned: {tables}")

    # 3) Table structure …
    structure = fetch_table_structure()
    print("Table Structure:", structure)

    # 4) Load PDF via environment variable (supports PDF_PATH or PDF_B64)
    pdf_data = load_pdf_from_env()
    if pdf_data is None:
        print("No PDF data available (either PDF_PATH/PDF_B64 was unset or file missing/invalid).")
    else:
        print("PDF loaded successfully.")

    # 5) Now pass pdf_data into your other functions
    user_input = (
        "I need a system design for a smart home energy management system that handles sensor data, "
        "optimizes energy usage, and allows remote control. Please consider the information provided in the attached document."
    )
    graph_data = { "user_requirements": user_input }

    examples_design = {
        "example_reqs": "Example system requirements: [Structured requirements similar to those from the dissertation].",
        "example_designs": "Example system designs: [Detailed design example]."
    }
    design_output = generate_system_designs(user_input, examples_design, pdf_data)
    print("\nGenerated System Design Document:")
    print(design_output)

    examples_verif = {
        "example_system_reqs": "Example system requirements: [Structured requirements based on the dissertation].",
        "example_verif_reqs": {"verification": {"details": [{"example": "verification requirement structure"}]}},
        "example_designs": {"design": {"details": [{"example": "system design structure"}]}}
    }
    verification_output = create_verification_requirements_models(user_input, examples_verif, pdf_data)
    print("\nGenerated Verification Requirements and Models:")
    print(verification_output)

    example_system_requirements = "Example system requirements: [Structured requirements for traceability]."
    example_system_designs = {"design": {"details": [{"example": "system design structure for traceability"}]}}
    traceability_output = get_traceability(user_input, example_system_requirements, example_system_designs)
    print("\nGenerated Traceability and Proof:")
    print(traceability_output)

    example_verification_requirements = {
        "verification": {"details": [{"example": "verification requirement structure for conditions"}]}
    }
    verification_conditions_output = get_verification_conditions(
        user_input,
        example_system_requirements,
        example_verification_requirements,
        example_system_designs
    )
    print("\nGenerated Verification Conditions:")
    print(verification_conditions_output)

    # Generate Graphviz-based visualization using the updated graph_data.
    svg_output = generate_network_visualization(graph_data, pdf_data)
    print("\nGenerated Graphviz-based Visualization (SVG):")
    print(svg_output)
