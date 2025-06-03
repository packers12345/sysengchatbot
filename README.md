# Systems_Engineering_Chatbot

## Overview
The Systems Engineering Chatbot is a Flask-based web application designed to assist users in generating system designs, verification requirements, and visualizations based on user inputs. It integrates with external APIs to provide intelligent responses and utilizes user authentication for secure access.

## Project Structure
```
Systems_Engineering_Chatbot
├── src
│   ├── app.py                # Main application file
│   ├── api_integration.py     # API integration functions
│   └── templates
│       ├── index.html        # Main index page template
│       └── login.html        # Login page template
├── requirements.txt          # Python dependencies
├── .env                      # Environment variables
└── README.md                 # Project documentation
```

## Setup Instructions

1. **Clone the Repository**
   ```
   git clone <repository-url>
   cd Systems_Engineering_Chatbot
   ```

2. **Create a Virtual Environment**
   ```
   python -m venv venv
   source venv/bin/activate  # On Windows use `venv\Scripts\activate`
   ```

3. **Install Dependencies**
   ```
   pip install -r requirements.txt
   ```

4. **Configure Environment Variables**
   Create a `.env` file in the root directory and add the following variables:
   ```
   API_KEY=<your_api_key>
   FLASK_SECRET_KEY=<your_secret_key>
   PDF_PATH=<path_to_your_pdf_file>
   PDF_B64=<base64_encoded_pdf>
   ```

5. **Run the Application**
   ```
   python src/app.py
   ```
   Access the application at `http://localhost:5000`.

## Usage
- Navigate to the login page to authenticate.
- After logging in, you can access the main index page where you can input prompts for system design and verification requirements.
- The application will generate responses based on the provided inputs and display visualizations.

