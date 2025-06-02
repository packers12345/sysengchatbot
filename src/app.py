import os
import base64
from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from io import BytesIO
import api_integration  # This module contains your integrated API, DB, and Graphormer-based visualization functions
from dotenv import load_dotenv
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import check_password_hash, generate_password_hash

# Load environment variables from .env file
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), ".env"))

# Set your API key, secret key, and PDF path from environment variables
api_key = os.environ.get("API_KEY")  # Use "API_KEY" to match your .env file
flask_secret_key = os.environ.get("FLASK_SECRET_KEY", "VT202527")
pdf_path = os.environ.get("PDF_PATH")
pdf_b64 = os.environ.get("PDF_B64")

if not api_key:
    print("WARNING: API_KEY environment variable not set! (Check your .env file and its location)")
else:
    api_integration.initialize_api(api_key)

if not pdf_path and not pdf_b64:
    print("WARNING: PDF_PATH or PDF_B64 environment variable not set! (Check your .env file and its location)")

app = Flask(__name__)
app.secret_key = flask_secret_key  # Get from environment or use default

# Setup Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"

# Simple user store (replace with DB in production)
USERS = {
    "Bhargav": {"password": generate_password_hash("Hume2027!")},
    "Adi": {"password": generate_password_hash("Hume2027!!")},
    "Dr.Wach": {"password": generate_password_hash("Hume2027!!!")},
    # Add up to 5 users as needed
}

class User(UserMixin):
    def __init__(self, username):
        self.id = username

    @staticmethod
    def authenticate(username, password):
        user = USERS.get(username)
        return user and check_password_hash(user["password"], password)

@login_manager.user_loader
def load_user(user_id):
    if user_id in USERS:
        return User(user_id)
    return None

# Load the PDF training data from environment variable path or base64
pdf_data = None
try:
    if pdf_path:
        with open(pdf_path, "rb") as f:
            pdf_data = BytesIO(f.read())
        print(f"PDF loaded from {pdf_path}")
    elif pdf_b64:
        pdf_bytes = base64.b64decode(pdf_b64)
        pdf_data = BytesIO(pdf_bytes)
        print("PDF loaded from PDF_B64 environment variable.")
    else:
        print("PDF path or PDF_B64 not set, skipping PDF load.")
except Exception as e:
    pdf_data = None
    print(f"Error loading PDF: {e}")

@app.route("/login", methods=["GET", "POST"])
def login():
    # Always log out the user before showing the login page
    if current_user.is_authenticated:
        logout_user()
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        if User.authenticate(username, password):
            login_user(User(username))
            return redirect(url_for("index"))
        else:
            return render_template("login.html", error="Invalid credentials"), 401
    return render_template("login.html")

@app.route("/logout")
@login_required
def logout():
    logout_user()
    return jsonify({"success": True, "message": "Logged out"})

@app.route("/")
@login_required
def index():
    # Initialize conversation history in session if not present
    if "conversation" not in session:
        session["conversation"] = []
    # Pass an initial null morphism image to the template
    return render_template("index.html", conversation=session.get("conversation", []), morphism_image=None)

@app.route("/combined", methods=["POST"])
@login_required
def combined():
    """
    Combined endpoint that retrieves outputs from the integration module:
      - System Design
      - Verification Requirements
      - Traceability
      - Verification Conditions
      - And the Morphism Visualization generated.
    """
    prompt = request.form.get("prompt", "").strip()
    if not prompt:
        return jsonify({"response": "Please enter a prompt."})
    
    # Example dictionaries for system design and verification requirements.
    examples_design = {
        "example_reqs": "Example system requirements: [Structured requirements based on the dissertation].",
        "example_designs": "Example system designs: [Detailed design example]."
    }
    examples_verif = {
        "example_system_reqs": "Example system requirements: [Structured requirements based on the dissertation].",
        "example_verif_reqs": {"verification": {"details": [{"example": "verification requirement structure"}]}},
        "example_designs": {"design": {"details": [{"example": "system design structure"}]}}
    }
    
    # Additional examples for traceability and verification conditions.
    example_system_requirements = "Example system requirements: [Structured requirements based on the dissertation]."
    example_system_designs = {"design": {"details": [{"example": "system design structure"}]}}
    example_verification_requirements = {"verification": {"details": [{"example": "verification requirement structure"}]}}

    # Generate outputs from the integration module.
    try:
        system_design_output = api_integration.generate_system_designs(prompt, examples_design, pdf_data)
    except Exception as e:
        system_design_output = f"Error generating system design: {str(e)}"
    
    try:
        verification_output = api_integration.create_verification_requirements_models(prompt, examples_verif, pdf_data)
    except Exception as e:
        msg = str(e)
        if "openai.ChatCompletion" in msg:
            msg += " Please run 'openai migrate' or install openai==0.28 to pin to the old version."
        verification_output = f"Error generating verification requirements: {msg}"
    
    try:
        traceability_output = api_integration.get_traceability(prompt, example_system_requirements, example_system_designs)
    except Exception as e:
        traceability_output = f"Error generating traceability: {str(e)}"
    
    try:
        verification_conditions_output = api_integration.get_verification_conditions(
            prompt,
            example_system_requirements,
            example_verification_requirements,
            example_system_designs
        )
    except Exception as e:
        verification_conditions_output = f"Error generating verification conditions: {str(e)}"
    
    # Generate the system visualization based on user input and generated outputs
    try:
        # Create graph data structure with user requirements
        graph_data = {
            'user_requirements': prompt,  # Pass the user's prompt as requirements
            'nodes': [],  # The API will generate nodes internally
            'edges': []   # The API will generate edges internally
        }
        
        # Generate the visualization using Graphviz for SysML-inspired diagrams
        morphism_image = api_integration.generate_network_visualization(graph_data, pdf_data)
        print("Length of visualization string:", len(morphism_image) if morphism_image else "None")
    except Exception as e:
        morphism_image = None
        print(f"Error generating system visualization: {e}")
        import traceback
        traceback.print_exc()

    # Update conversation history
    conversation = session.get("conversation", [])
    conversation.append({"sender": "User", "text": prompt})
    combined_text = (
        "=== System Design ===\n" + system_design_output + "\n\n" +
        "=== Verification Requirements ===\n" + verification_output + "\n\n" +
        "=== Traceability ===\n" + traceability_output + "\n\n" +
        "=== Verification Conditions ===\n" + verification_conditions_output
    )
    conversation.append({"sender": "Assistant", "text": combined_text})
    session["conversation"] = conversation

    # Return the outputs including the system visualization
    return jsonify({
        "system_design": system_design_output,
        "verification_requirements": verification_output,
        "traceability": traceability_output,
        "verification_conditions": verification_conditions_output,
        # Pass the SVG string directly for frontend rendering
        "system_visual": morphism_image
    })

@app.route("/whoami")
@login_required
def whoami():
    return jsonify({"user": current_user.id})

if __name__ == "__main__":
    # Get port from environment variable for cloud deployment compatibility
    port = int(os.environ.get("PORT", 5000))
    # Set host to 0.0.0.0 to make it accessible outside container
    app.run(host='0.0.0.0', port=5000, debug=False)
