import os
import re
import json
import base64
import requests
import pypyodbc as odbc
import PyPDF2
import spacy
import graphviz
from io import BytesIO
from typing import Dict, List, Any, Optional
from dotenv import load_dotenv
import google.generativeai as genai # Changed from 'import openai'

# Note: pyvis and networkx are imported but not used in the provided functions.
# Keeping them if you intend to add network visualization functionality later.
from pyvis.network import Network
import networkx as nx

# Load environment variables at the very beginning of the script execution
# This ensures that os.environ is populated before any functions try to access keys.
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), ".env"))

# Load spaCy model
try:
    nlp = spacy.load("en_core_web_sm")
except OSError:
    print("Downloading spaCy model 'en_core_web_sm'. This will happen once.")
    spacy.cli.download("en_core_web_sm")
    nlp = spacy.load("en_core_web_sm")

def get_gemini_client():
    """
    Retrieves the Gemini API key from environment variables and configures the Gemini client.
    Returns the configured generative model instance.
    """
    gemini_api_key = os.environ.get("GEMINI_API_KEY")
    if not gemini_api_key:
        raise ValueError(
            "Missing Gemini API key. Set GEMINI_API_KEY environment variable in your .env file."
        )
    genai.configure(api_key=gemini_api_key)
    # Using gemini-2.0-flash for text generation
    return genai.GenerativeModel('gemini-2.0-flash')

# --- DB Functions ---
def connect_to_db():
    """Establishes a connection to the SQL Server database using environment variables."""
    server = os.environ.get("DB_SERVER")
    database = os.environ.get("DB_NAME")
    username = os.environ.get("DB_USER")
    password = os.environ.get("DB_PASSWORD")

    if not all([server, database, username, password]):
        print("DB environment variables (DB_SERVER, DB_NAME, DB_USER, DB_PASSWORD) missing.")
        return None

    conn_str = (
        f"Driver={{ODBC Driver 18 for SQL Server}};"
        f"Server=tcp:{server},1433;"
        f"Database={database};"
        f"Uid={username};Pwd={password};"
        "Encrypt=yes;TrustServerCertificate=no;Connection Timeout=30;"
    )
    try:
        return odbc.connect(conn_str)
    except Exception as e:
        print(f"DB connection error: {e}")
        return None

def list_all_tables() -> List[str]:
    """Lists all tables in the 'dbo' schema of the connected database."""
    conn = connect_to_db()
    if not conn:
        return []
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA = 'dbo';")
        return [row[0] for row in cursor.fetchall()]
    except Exception as e:
        print(f"Error listing tables: {e}")
        return []
    finally:
        if conn:
            conn.close()

def fetch_table_structure() -> Dict[str, Dict[str, str]]:
    """Fetches the column names and data types for all tables in the database."""
    conn = connect_to_db()
    if not conn:
        return {}
    structure = {}
    try:
        cursor = conn.cursor()
        for table in list_all_tables():
            cursor.execute(f"SELECT COLUMN_NAME, DATA_TYPE FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = '{table}';")
            structure[table] = {col[0]: col[1] for col in cursor.fetchall()}
        return structure
    except Exception as e:
        print(f"Error fetching table structure: {e}")
        return {}
    finally:
        if conn:
            conn.close()

def fetch_specific_table(table_name: str, limit: int = 5) -> List[Any]:
    """Fetches a limited number of rows from a specified table."""
    conn = connect_to_db()
    if not conn:
        return []
    try:
        cursor = conn.cursor()
        if not re.match(r'^\w+$', table_name):
            raise ValueError("Invalid table name. Contains disallowed characters.")
        # Sanitize limit to prevent SQL injection (though int() already helps)
        if not isinstance(limit, int) or limit <= 0:
            limit = 5
        cursor.execute(f"SELECT TOP {limit} * FROM {table_name};")
        return cursor.fetchall()
    except Exception as e:
        print(f"Error fetching specific table '{table_name}': {e}")
        return []
    finally:
        if conn:
            conn.close()

def detect_table_name(user_text: str) -> str:
    """Detects a potential table name mentioned in the user's input."""
    # This regex looks for 'table' followed by one or more word characters
    match = re.search(r'\btable\s+([a-zA-Z0-9_]+)', user_text, re.IGNORECASE)
    return match.group(1) if match else ""

# --- NLP and PDF ---
def enhance_user_requirements(user_text: str) -> str:
    """Uses spaCy to extract key phrases and entities to enhance user requirements."""
    doc = nlp(user_text)
    key_phrases = {chunk.text.strip() for chunk in doc.noun_chunks}
    key_phrases |= {ent.text.strip() for ent in doc.ents}
    output = user_text.strip()
    if key_phrases:
        output += "\nKey concepts: " + ", ".join(sorted(list(key_phrases))) # Sorted for consistent output
    if len(user_text.split()) < 20:
        output += "\n[Note: The input is brief; more detail may yield a richer design.]"
    return output

def extract_text_from_pdf(pdf_file: BytesIO) -> str:
    """Extracts text from a BytesIO object representing a PDF file."""
    text = ""
    try:
        reader = PyPDF2.PdfReader(pdf_file)
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text: # Only append if text was extracted
                text += page_text + "\n"
    except PyPDF2.errors.PdfReadError:
        print("Error reading PDF file: Corrupted or encrypted PDF.")
    except Exception as e:
        print(f"An unexpected error occurred while extracting PDF text: {e}")
    return text.strip()

def generate_system_designs(user_requirements: str, examples: Optional[Any] = None, pdf_data: Optional[BytesIO] = None) -> str:
    """
    Generates a practical system design document based on user requirements,
    database structure, and optional PDF context using Gemini AI.
    """
    try:
        processed = enhance_user_requirements(user_requirements)
        table_structure = fetch_table_structure()

        # Get relevant table data if referenced
        table_info = ""
        referenced = detect_table_name(user_requirements)
        if referenced:
            rows = fetch_specific_table(referenced)
            if rows:
                table_info = f"\nRelevant database data from {referenced}:\n"
                table_info += "\n".join([f"Row {i+1}: {row}" for i, row in enumerate(rows[:3])])
            else:
                table_info = f"\nNote: Table '{referenced}' referenced, but no data found or table does not exist."

        # Include PDF data if available
        pdf_context = ""
        if pdf_data:
            extracted_pdf_text = extract_text_from_pdf(pdf_data)
            if extracted_pdf_text:
                pdf_context = f"\nReference document context:\n{extracted_pdf_text[:1000]}..."
            else:
                pdf_context = "\nNote: PDF provided, but no extractable text or file is empty/corrupted."

        prompt = f"""
You are a systems engineer. Generate a practical system design document for the following requirements:

User Requirements:
{processed}

Database Structure Available:
{table_structure}
{table_info}
{pdf_context}

Create a system design document that includes:

1. **System Overview**: Brief description of the system's purpose and scope
2. **Functional Requirements**: 5-7 clear, testable functional requirements
3. **Non-Functional Requirements**: Performance, safety, and operational requirements
4. **System Architecture**: High-level components and their interactions
5. **Interface Specifications**: Key inputs, outputs, and data flows
6. **Implementation Considerations**: Technology choices and constraints

Format the response clearly with headers and bullet points. Keep it practical and implementable. Discuss the mathematical foundation as well
Avoid unnecessary mathematical notation unless specifically required for the domain.
"""
        model = get_gemini_client()
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        return f"Error generating system designs: {e}"

def create_verification_requirements_models(system_requirements: str, examples: Optional[Any] = None, pdf_data: Optional[BytesIO] = None) -> str:
    """
    Generates practical verification requirements based on system requirements and optional PDF context using Gemini AI.
    """
    try:
        processed = enhance_user_requirements(system_requirements)

        pdf_context = ""
        if pdf_data:
            extracted_pdf_text = extract_text_from_pdf(pdf_data)
            if extracted_pdf_text:
                pdf_context = f"\nReference context:\n{extracted_pdf_text[:800]}..."
            else:
                pdf_context = "\nNote: PDF provided, but no extractable text or file is empty/corrupted."

        prompt = f"""
You are a systems engineer creating verification requirements. Based on these system requirements:

{processed}
{pdf_context}

Generate a verification and validation plan that includes:

1. **Verification Strategy**: How to verify each requirement is correctly implemented. Discuss the mathematical foundation as well
2. **Test Categories**:
   - Unit tests for individual components
   - Integration tests for system interactions
   - System tests for end-to-end functionality
   - Acceptance tests for user requirements
3. **Key Test Cases**: Specific test scenarios with expected outcomes
4. **Validation Criteria**: Measurable criteria for success
5. **Test Environment**: Required test setup and conditions
6. **Risk Mitigation**: How to handle potential test failures

Keep the response practical and focused on implementable testing strategies.
"""
        model = get_gemini_client()
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        return f"Error generating verification requirements: {e}"

def get_traceability(system_requirements: str, example_system_requirements: Optional[Any] = None, example_designs: Optional[Any] = None) -> str:
    """
    Generates a practical traceability matrix based on system requirements using Gemini AI.
    """
    try:
        prompt = f"""
Create a traceability matrix for these system requirements:

{system_requirements}

Generate a clear traceability analysis that includes:

1. **Requirements Traceability Matrix**: Table showing:
   - Requirement ID
   - Requirement Description
   - Source (user need, regulation, etc.)
   - Verification Method
   - Implementation Status

2. **Forward Traceability**: How requirements trace to design elements
3. **Backward Traceability**: How design elements trace back to requirements
4. **Coverage Analysis**: Identification of any gaps or orphaned requirements

Present this as a clear table and analysis, not complex mathematical proofs.
"""
        model = get_gemini_client()
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        return f"Error generating traceability: {e}"

def get_verification_conditions(system_requirements: str, example_system_reqs: Optional[Any] = None, example_verif_reqs: Optional[Any] = None, example_designs: Optional[Any] = None) -> str:
    """
    Generates practical verification conditions for system requirements using Gemini AI.
    """
    try:
        prompt = f"""
Define verification conditions for these system requirements:

{system_requirements}

Create verification conditions that specify:

1. **Preconditions**: What must be true before testing each requirement
2. **Test Procedures**: Step-by-step procedures to verify each requirement
3. **Expected Outcomes**: What constitutes successful verification
4. **Pass/Fail Criteria**: Clear criteria for determining test success
5. **Test Data Requirements**: What data is needed for testing
6. **Environmental Conditions**: Required test environment setup

Focus on practical, executable verification procedures rather than theoretical proofs.
"""
        model = get_gemini_client()
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        return f"Error generating verification conditions: {e}"

def generate_system_requirements(prompt: str, pdf_data: Optional[BytesIO] = None) -> str:
    """
    Generates clear, actionable system requirements based on user input,
    database context, and optional PDF data using Gemini AI.
    """
    try:
        processed = enhance_user_requirements(prompt)
        table_structure = fetch_table_structure()

        # Get table data if referenced
        table_info = ""
        referenced_table = detect_table_name(prompt)
        if referenced_table:
            rows = fetch_specific_table(referenced_table)
            if rows:
                table_info = f"\nDatabase context from {referenced_table}:\n"
                table_info += "\n".join([f"Row {i+1}: {row}" for i, row in enumerate(rows[:3])])
            else:
                table_info = f"\nNote: Table '{referenced_table}' referenced, but no data found or table does not exist."

        pdf_text = ""
        if pdf_data:
            extracted_pdf_text = extract_text_from_pdf(pdf_data)
            if extracted_pdf_text:
                pdf_text = f"\nReference document:\n{extracted_pdf_text[:1000]}..."
            else:
                pdf_text = "\nNote: PDF provided, but no extractable text or file is empty/corrupted."

        query = f"""
You are a systems engineer. Generate clear, implementable system requirements based on this input:

User Input: {processed}
{pdf_text}
{table_info}

Create 8-12 system requirements that are:
- Specific and measurable
- Testable and verifiable
- Necessary and sufficient
- Clearly written in "shall" statements

Organize them into categories:
1. **Functional Requirements**: What the system must do
2. **Performance Requirements**: Speed, capacity, efficiency metrics
3. **Interface Requirements**: How the system interacts with users/other systems
4. **Safety Requirements**: Safety and security considerations
5. **Operational Requirements**: Maintenance, reliability, availability

Format each requirement as:
REQ-[CATEGORY]-[NUMBER]: The system SHALL [specific requirement] [measurable criteria]

Example:
REQ-FUNC-001: The system SHALL process user requests within 2 seconds of receipt
REQ-PERF-002: The system SHALL support up to 1000 concurrent users
"""
        model = get_gemini_client()
        response = model.generate_content(query)
        return response.text.strip()
    except Exception as e:
        return f"Error generating system requirements: {e}"

# Placeholder for generate_network_visualization as it was referenced in app.py but not defined here.
# You will need to implement this function if you want to use it.
def generate_network_visualization(graph_data: Dict[str, Any], pdf_data: Optional[BytesIO] = None) -> Optional[str]:
    """
    Placeholder function for generating a network visualization.
    This function was called in app.py but is not defined in the original api_integration.py.
    It currently returns None and prints a message.
    You need to implement the actual visualization logic here using networkx and pyvis.
    """
    print("WARNING: generate_network_visualization function is a placeholder and needs implementation.")
    print("Graph data received:", graph_data)
    # Example basic implementation using networkx and pyvis:
    try:
        if not graph_data or not graph_data.get('nodes'):
            print("No graph data (nodes) provided for visualization.")
            return None

        # Create a NetworkX graph
        G = nx.Graph()

        # Add nodes
        for node in graph_data.get('nodes', []):
            G.add_node(node.get('id'), label=node.get('label', node.get('id')), title=node.get('title', ''))

        # Add edges
        for edge in graph_data.get('edges', []):
            G.add_edge(edge.get('source'), edge.get('target'), title=edge.get('title', ''))

        # Create a PyVis network
        net = Network(notebook=False, height="750px", width="100%", directed=False, cdn_resources='remote')
        net.from_nx(G)

        # Save to a temporary HTML file and return its content
        html_path = "temp_visualization.html"
        net.save_html(html_path)
        with open(html_path, 'r', encoding='utf-8') as f:
            html_content = f.read()
        os.remove(html_path) # Clean up temp file
        return html_content

    except Exception as e:
        print(f"Error in generate_network_visualization (placeholder implementation): {e}")
        return None
