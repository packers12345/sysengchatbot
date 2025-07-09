import os
import re
import json
import base64
import requests
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

# --- NLP ---
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

def generate_system_designs(user_requirements: str, examples: Optional[Any] = None) -> str:
    """
    Generates a practical system design document based on user requirements
    using Gemini AI.
    """
    try:
        processed = enhance_user_requirements(user_requirements)

        prompt = f"""
You are a systems engineer. Generate a practical system design document for the following requirements:

User Requirements:
{processed}

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

def create_verification_requirements_models(system_requirements: str, examples: Optional[Any] = None) -> str:
    """
    Generates practical verification requirements based on system requirements using Gemini AI.
    """
    try:
        processed = enhance_user_requirements(system_requirements)

        prompt = f"""
You are a systems engineer creating verification requirements. Based on these system requirements:

{processed}

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

def generate_system_requirements(prompt: str) -> str:
    """
    Generates clear, actionable system requirements based on user input
    using Gemini AI.
    """
    try:
        processed = enhance_user_requirements(prompt)

        query = f"""
You are a systems engineer. Generate clear, implementable system requirements based on this input:

User Input: {processed}

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
def generate_network_visualization(graph_data: Dict[str, Any]) -> Optional[str]:
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
