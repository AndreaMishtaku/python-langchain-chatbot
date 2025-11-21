# Basic AI Assistant

FastAPI/Langchain simple chatbot using OpenAI. Interact with user based on similarity search performed in knowledge base. Leveraged langaraph agent with tools.

---

## Prerequisites

- Python 3.12
- Deployed models on Azure AI
- sqlite & Chroma DB

## Run the application

1. Create a virtual environment:

```bash
python -m venv venv
```

2. Activate the virtual environment:

   - **Windows:**

     ```bash
     venv\Scripts\activate
     ```

   - **Linux/macOS:**

     ```bash
     source venv/bin/activate
     ```

3. Install dependencies:

```bash
pip install -r requirements.txt
```

4. Set up environment variables:
   Create a .env file in the root directory of the project and fill it according to env.template guide.

5. Run the FastAPI application:

```bash
python main.py
```
