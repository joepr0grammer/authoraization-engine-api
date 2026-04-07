# AuthorAIzation Engine - Backend (The Zero-Trust Bouncer)

This is the Python/FastAPI backend for the **AuthorAIzation Engine**. It serves as the core Zero-Trust security layer, sitting between our Next.js frontend, our LangChain AI agent, and the GitHub API. 

This backend is responsible for intercepting high-stakes AI intent, managing Machine-to-Machine (M2M) authentication via Auth0's Token Vault, and enforcing out-of-band human authorization (CIBA) before any execution occurs.

## Key Features

* **FastAPI Router:** High-performance, async API endpoints to handle frontend chat requests and agent routing.
* **LangChain Intelligence Layer:** Wraps the core LLM with specific, sandboxed tools (e.g., `read_github_issues`, `read_github_prs`).
* **The "Smart Vault" Keymaster:** Dynamically switches between extracting a live, vaulted GitHub token via Auth0 M2M authentication (for production) and using a securely scoped Service Account PAT (for the hackathon demo sandbox).
* **CIBA Intercept:** Hard-locks execution on state-changing actions (like merging a Pull Request) until out-of-band cryptographic approval is received.

## Prerequisites

Before you begin, ensure you have the following installed:
* [Python 3.9+](https://www.python.org/downloads/)
* pip (Python package installer)
* An [Auth0](https://auth0.com/) Tenant with a Machine-to-Machine application configured.
* An OpenAI API Key (or equivalent LLM provider for LangChain).

## Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/joepr0grammer/authoraization-backend.git
   cd authoraization-backend
2. **Create and activate a virtual environment:**
    ```bash
    python -m venv venv

    # On macOS/Linux:
    source venv/bin/activate
    # On Windows:
    venv\Scripts\activate
3. **Install dependencies:**
    ```bash
    pip install -r requirements.txt
4. **Configuration**
    ```bash
    # AI Provider
    OPENAI_API_KEY=your_openai_api_key

    # Auth0 M2M Configuration (For Token Vault Retrieval)
    AUTH0_DOMAIN=your-auth0-tenant.auth0.com
    M2M_CLIENT_ID=your_m2m_client_id
    M2M_CLIENT_SECRET=your_m2m_client_secret

    # GitHub Sandbox Configuration
    GITHUB_REPO_NAME=yourusername/your-sandbox-repo
    GITHUB_SETUP_PAT=your_service_account_github_pat
5. **Running the Development Server**
    ```bash
    # AI Provider
    uvicorn main:app --reload --port 8000
## System Architecture Note
This backend must run concurrently with the Next.js Frontend for the full user experience. Ensure that the frontend's .env.local is pointing to the correct port (default is 8000) where this FastAPI instance is running.