from fastapi import FastAPI, Depends, HTTPException, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from jose import jwt
import requests
import os
import contextvars # <--- NEW IMPORT
from github import Github # <--- NEW IMPORT

# --- LANGCHAIN & OPENAI IMPORTS ---
from langchain_openai import ChatOpenAI
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage

from dotenv import load_dotenv

# Load secrets from the .env file
load_dotenv()

os.environ["OPENAI_API_KEY"] = os.getenv("OPENAI_API_KEY")
M2M_CLIENT_ID = os.getenv("M2M_CLIENT_ID")
M2M_CLIENT_SECRET = os.getenv("M2M_CLIENT_SECRET")



app = FastAPI(title="AuthorAIzation Agent API")
security = HTTPBearer()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000", 
        "https://authoraization-engine-web.vercel.app"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==========================================
# 1. ENVIRONMENT VARIABLES
# ==========================================
AUTH0_DOMAIN = "dev-tdkff1c8x363tz4a.us.auth0.com" 
API_AUDIENCE = "https://authoraization-api.local" 
ALGORITHMS = ["RS256"]
GITHUB_REPO_NAME = "AuthorAIzation-Sandbox/production-backend"

# This holds the Auth0 ID of whoever is currently chatting
current_user_id = contextvars.ContextVar("current_user_id")

# ==========================================
# 2. THE BOUNCER & THE VAULT FETCHER
# ==========================================
def verify_token(credentials: HTTPAuthorizationCredentials = Security(security)):
    # ... (Keep your exact existing verify_token code here) ...
    token = credentials.credentials
    try:
        jwks_url = f'https://{AUTH0_DOMAIN}/.well-known/jwks.json'
        jwks = requests.get(jwks_url).json()
        unverified_header = jwt.get_unverified_header(token)
        rsa_key = next((key for key in jwks["keys"] if key["kid"] == unverified_header["kid"]), None)
        
        if rsa_key:
            return jwt.decode(
                token, rsa_key, algorithms=ALGORITHMS,
                audience=API_AUDIENCE, issuer=f"https://{AUTH0_DOMAIN}/"
            )
    except Exception as e:
        print(f"\n[BOUNCER REJECTED TOKEN]: {str(e)}\n") 
        raise HTTPException(status_code=401, detail=str(e))
    raise HTTPException(status_code=401, detail="Invalid token")

def get_vaulted_github_token(user_id: str) -> str:
    """The Keymaster: Securely retrieves the GitHub PAT from Auth0"""
    # 1. Get an access token for the Auth0 Management API
    token_url = f"https://{AUTH0_DOMAIN}/oauth/token"
    payload = {
        "client_id": M2M_CLIENT_ID,
        "client_secret": M2M_CLIENT_SECRET,
        "audience": f"https://{AUTH0_DOMAIN}/api/v2/",
        "grant_type": "client_credentials"
    }
    mgmt_token = requests.post(token_url, json=payload).json().get("access_token")

    # 2. Fetch the User's Profile (which contains the vaulted tokens)
    user_url = f"https://{AUTH0_DOMAIN}/api/v2/users/{user_id}"
    user_data = requests.get(user_url, headers={"Authorization": f"Bearer {mgmt_token}"}).json()

    # 3. Dig through their identities to find the GitHub token
    for identity in user_data.get("identities", []):
        if identity.get("provider") == "github":
            return identity.get("access_token")
            
    raise Exception("No vaulted GitHub token found for this user!")

# ==========================================
# 3. THE LIVE AI TOOLS
# ==========================================
@tool
def read_github_issues() -> str:
    """Use this tool to read open issues in the GitHub repository."""
    try:
        print("\n[TOKEN VAULT] Securely fetching user's GitHub token from Auth0...")
        user_id = current_user_id.get()
        gh_token = get_vaulted_github_token(user_id)
        
        print("[TOOL EXECUTING] Hitting live GitHub API...")
        g = Github(gh_token)
        repo = g.get_repo(GITHUB_REPO_NAME)
        open_issues = repo.get_issues(state='open')
        
        if open_issues.totalCount == 0:
            return "There are currently no open issues in the repository."
        
        # Add a bullet point to the start of each issue
        issue_list = [f"• Issue #{issue.number}: {issue.title}" for issue in open_issues[:3]]
        
        # Join them with a newline character instead of a pipe!
        return "\n".join(issue_list)
        
    except Exception as e:
        return f"CRITICAL ERROR reading GitHub issues: {str(e)}"
    
@tool
def merge_github_pr(pr_number: int) -> str:
    """Use this tool ONLY to merge a Pull Request in GitHub."""
    return f"ACTION_BLOCKED_PENDING_APPROVAL_FOR_PR_{pr_number}"

llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
tools = [read_github_issues, merge_github_pr]
agent = llm.bind_tools(tools)

# ==========================================
# 4. THE API ENDPOINT
# ==========================================
class ChatRequest(BaseModel):
    prompt: str

@app.post("/api/chat")
def chat_with_agent(request: ChatRequest, current_user: dict = Depends(verify_token)):
    user_id = current_user.get("sub")
    
    # Save the user_id into context so the LangChain tool can grab it!
    current_user_id.set(user_id)
    
    print(f"\n[AGENT] Analyzing prompt from {user_id}: {request.prompt}")
    response = agent.invoke([HumanMessage(content=request.prompt)])
    
    if response.tool_calls:
        tool_call = response.tool_calls[0]
        tool_name = tool_call["name"]
        
        if tool_name == "read_github_issues":
            live_data = read_github_issues.invoke({})
            return {"status": "success", "message": "Agent securely read live GitHub issues via Auth0 Token Vault.", "data": live_data}
            
        elif tool_name == "merge_github_pr":
            pr_num = tool_call["args"].get("pr_number")
            return {
                "status": "pending_ciba", 
                "pr_number": pr_num, # <--- ADD THIS SO NEXT.JS KNOWS WHICH PR TO MERGE
                "message": f"High-Stakes Action Detected! Intercepting merge request for PR #{pr_num}. Initiating Auth0 Push Notification to human..."
            }            
    return {"status": "success", "message": response.content}

class ApproveRequest(BaseModel):
    pr_number: int

@app.post("/api/approve-ciba")
def approve_ciba(request: ApproveRequest, current_user: dict = Depends(verify_token)):
    try:
        print(f"\n[CIBA] Out-of-band approval received for PR #{request.pr_number}!")
        user_id = current_user.get("sub")
        gh_token = get_vaulted_github_token(user_id)
        
        # Connect to GitHub and Merge
        g = Github(gh_token)
        repo = g.get_repo(GITHUB_REPO_NAME)
        pr = repo.get_pull(request.pr_number)
        
        pr.merge(commit_message="Merged securely via AuthorAIzation CIBA Push flow.")
        
        return {"status": "success", "message": f"Secure merge executed successfully for PR #{request.pr_number}."}
    except Exception as e:
        return {"status": "error", "message": f"Merge failed: {str(e)}"}
    
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)