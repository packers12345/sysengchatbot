# Use an official Python runtime as a parent image
FROM python:3.10-slim-bullseye

# Ensure all system packages are up to date to reduce vulnerabilities
RUN apt-get update && apt-get upgrade -y && \
    apt-get install -y --no-install-recommends build-essential gcc unixodbc unixodbc-dev graphviz && \
    rm -rf /var/lib/apt/lists/*

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Set the working directory
WORKDIR /app

# Copy requirements
COPY requirements.txt .

# Install Python dependencies
RUN pip install --upgrade pip
# Install torch CPU-only first (remove torch from requirements.txt)
RUN pip install torch==2.3.1+cpu -f https://download.pytorch.org/whl/torch_stable.html
RUN pip install -r requirements.txt

# Download the English language model for spaCy
RUN python -m spacy download en_core_web_sm

# Copy project files
COPY . .

# Expose the port Flask runs on
EXPOSE 5000

# Set environment variables for Flask
ENV FLASK_APP=src/app.py

# Run the Flask app
CMD ["python", "src/app.py"]