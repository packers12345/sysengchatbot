import os
import requests
from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from io import BytesIO
import api_integration # Import the updated api_integration module
from dotenv import load_dotenv
# Removed Flask-Login imports as login functionality is being removed
# from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash # Keep generate_password_hash if still needed elsewhere, though not for login now

# Load environment variables from .env file
# This should be done at the very top to ensure variables are available
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), ".env"))

# Retrieve API key and PDF path from environment variables
gemini_api_key = os.environ.get("GEMINI_API_KEY")
pdf_path = os.environ.get("PDF_PATH")

# --- Initial Warnings for Missing Environment Variables ---
if not gemini_api_key:
    print("WARNING: GEMINI_API_KEY not set in .env! AI functionalities may fail.")
else:
    print("Gemini API key detected. AI functionalities should be available.")

if not pdf_path:
    print("WARNING: PDF_PATH not set in .env! PDF processing functionalities may be limited.")
else:
    print(f"PDF_PATH set to: {pdf_path}")

app = Flask(__name__)
# Flask secret key for session management, retrieved from environment
# Still needed for session management, even without explicit login
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "A_DEFAULT_SECRET_KEY_IF_NOT_SET")
if app.secret_key == "A_DEFAULT_SECRET_KEY_IF_NOT_SET":
    print("WARNING: FLASK_SECRET_KEY not set in .env! Using a default key. Please set a strong, random key for production.")


# --- Flask-Login Setup (Removed) ---
# login_manager = LoginManager()
# login_manager.init_app(app)
# login_manager.login_view = "login"

# --- User Management (Removed) ---
# The get_users, User, USERS, and load_user functions are no longer needed
# as there is no login system.
# def get_users(): ...
# USERS = get_users()
# class User(UserMixin): ...
# @login_manager.user_loader ...


# --- PDF Data Loading ---
pdf_data = None
try:
    if pdf_path:
        if pdf_path.startswith("http"):
            # Fetch PDF from a URL
            print(f"Attempting to fetch PDF from URL: {pdf_path}")
            response = requests.get(pdf_path, timeout=10) # Added timeout
            response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)
            pdf_data = BytesIO(response.content)
            print("PDF fetched successfully from URL.")
        else:
            # Load PDF from a local file path
            if os.path.exists(pdf_path):
                print(f"Attempting to load PDF from local path: {pdf_path}")
                with open(pdf_path, "rb") as f:
                    pdf_data = BytesIO(f.read())
                print("PDF loaded successfully from local path.")
            else:
                print(f"ERROR: Local PDF file not found at: {pdf_path}")
                pdf_data = None
except requests.exceptions.RequestException as e:
    print(f"ERROR: Failed to fetch PDF from URL '{pdf_path}': {e}")
    pdf_data = None
except Exception as e:
    print(f"ERROR: An unexpected error occurred while loading PDF: {e}")
    pdf_data = None

# --- Routes ---
# Removed /login route
# @app.route("/login", methods=["GET", "POST"])
# def login(): ...

# Removed /logout route
# @app.route("/logout", methods=["GET", "POST"])
# @login_required
# def logout(): ...

@app.route("/")
# Removed @login_required decorator
def index():
    """Renders the main chatbot interface."""
    # Ensure conversation is initialized for all users
    if "conversation" not in session:
        session["conversation"] = []
    # Pass an initial None for morphism_image, it will be updated via AJAX
    return render_template("index.html", conversation=session["conversation"], morphism_image=None)

@app.route("/combined", methods=["POST"])
# Removed @login_required decorator
def combined():
    """
    Processes a user prompt to generate system design, verification requirements,
    traceability, verification conditions, and a system visualization.
    """
    prompt = request.form.get("prompt", "").strip()
    if not prompt:
        return jsonify({"response": "Please enter a prompt."}), 400 # Return 400 for bad request

    system_design_output = "Error: System design generation failed."
    verification_output = "Error: Verification requirements generation failed."
    traceability_output = "Error: Traceability generation failed."
    verification_conditions_output = "Error: Verification conditions generation failed."
    morphism_image = None # Initialize to None

    try:
        system_design_output = api_integration.generate_system_designs(prompt, pdf_data=pdf_data)
    except Exception as e:
        print(f"Error calling generate_system_designs: {e}")
        system_design_output = f"Error generating system design: {str(e)}"

    try:
        verification_output = api_integration.create_verification_requirements_models(prompt, pdf_data=pdf_data)
    except Exception as e:
        print(f"Error calling create_verification_requirements_models: {e}")
        verification_output = f"Error generating verification requirements: {str(e)}"

    try:
        traceability_output = api_integration.get_traceability(prompt)
    except Exception as e:
        print(f"Error calling get_traceability: {e}")
        traceability_output = f"Error generating traceability: {str(e)}"

    try:
        verification_conditions_output = api_integration.get_verification_conditions(prompt)
    except Exception as e:
        print(f"Error calling get_verification_conditions: {e}")
        verification_conditions_output = f"Error generating verification conditions: {str(e)}"

    try:
        # Prepare graph data for visualization.
        # This structure should match what generate_network_visualization expects.
        graph_data = {
            'user_requirements': prompt,
            'nodes': [], # You'll need to populate these based on your design logic
            'edges': []  # You'll need to populate these based on your design logic
        }
        # Call the visualization function
        morphism_image = api_integration.generate_network_visualization(graph_data, pdf_data)
    except Exception as e:
        morphism_image = None
        print(f"Error generating visualization: {e}")

    # Update conversation history in session
    conversation = session.get("conversation", [])
    conversation.append({"sender": "User", "text": prompt})
    combined_text = (
        "=== System Design ===\n" + system_design_output + "\n\n" +
        "=== Verification Requirements ===\n" + verification_output + "\n\n" +
        "=== Traceability ===\n" + traceability_output + "\n\n" +
        "=== Verification Conditions ===\n" + verification_conditions_output
    )
    conversation.append({"sender": "Assistant", "text": combined_text})
    session["conversation"] = conversation # Save updated conversation to session

    # Return all generated outputs as JSON
    return jsonify({
        "system_design": system_design_output,
        "verification_requirements": verification_output,
        "traceability": traceability_output,
        "verification_conditions": verification_conditions_output,
        "system_visual": morphism_image # This will be HTML content for the visualization
    })

@app.route("/system_requirements", methods=["POST"])
# Removed @login_required decorator
def system_requirements():
    """Generates only system requirements based on a prompt."""
    prompt = request.form.get("prompt", "").strip()
    if not prompt:
        return jsonify({"response": "Please enter a prompt."}), 400

    try:
        system_requirements_text = api_integration.generate_system_requirements(prompt, pdf_data=pdf_data)
        return jsonify({
            "system_requirements": system_requirements_text
        })
    except Exception as e:
        print(f"Error calling generate_system_requirements: {e}")
        return jsonify({"error": f"Failed to generate system requirements: {str(e)}"}), 500

# Removed /whoami route as it's tied to user authentication
# @app.route("/whoami")
# @login_required
# def whoami(): ...

# --- Main Application Run ---
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    # Running in debug mode is useful for development, but should be False in production
    app.run(host="0.0.0.0", port=port, debug=True)