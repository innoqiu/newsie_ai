"""
FastAPI server for NewsieAI backend API.
Handles user profile management and agent interactions.
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
from typing import List, Optional
import asyncio
import json
from datetime import datetime

# Import agents
try:
    from agents.personal_assistant import run_personal_assistant
    from agents.retriv import retriv_run_agent
except ImportError as e:
    print(f"Import Error: {e}")
    print("Ensure you are running from the backend directory")

# Import database functions
try:
    from database import save_user_profile, get_user_profile, get_user_profile_by_email
except ImportError as e:
    print(f"Database import error: {e}")
    print("Database functions may not be available")

app = FastAPI(title="NewsieAI API", version="1.0.0")

# Initialize database on startup
@app.on_event("startup")
async def startup_event():
    """Initialize database when API server starts"""
    try:
        from database import init_database
        init_database()
        print("Database initialized on API server startup")
    except ImportError:
        print("Warning: Database module not available")
    except Exception as e:
        print(f"Warning: Database initialization failed: {e}")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =================================================================
# Pydantic Models
# =================================================================

class UserProfileRequest(BaseModel):
    """User profile data from frontend"""
    name: str  # What should I call you
    email: EmailStr  # Where to send your news
    notification_time: str  # When to receive news (format: "HH:MM" or "HH:MM,HH:MM" for multiple)
    interests: str  # User interests (comma-separated or free text)

class UserProfileResponse(BaseModel):
    """Response after profile creation"""
    status: str
    message: str
    user_id: str
    profile: dict

class NewsRequestRequest(BaseModel):
    """Request to get news based on profile"""
    user_id: Optional[str] = None
    content_query: Optional[str] = None

class NewsRequestResponse(BaseModel):
    """Response with news content"""
    status: str
    content: Optional[str] = None
    message: Optional[str] = None

class CheckProfileRequest(BaseModel):
    """Request to check user profile"""
    email: EmailStr

# =================================================================
# API Endpoints
# =================================================================

@app.get("/")
async def root():
    """Health check endpoint"""
    return {"status": "ok", "message": "NewsieAI API is running"}

@app.post("/api/profile", response_model=UserProfileResponse)
async def create_user_profile(profile: UserProfileRequest):
    """
    Create or update user profile.
    
    Receives:
    - name: What to call the user
    - email: Where to send news
    - notification_time: When to receive news (HH:MM format, comma-separated for multiple)
    - interests: User interests (comma-separated or free text)
    """
    try:
        # Parse notification times
        notification_times = []
        if profile.notification_time:
            times = [t.strip() for t in profile.notification_time.split(",") if t.strip()]
            notification_times = times
        
        # Parse interests
        interests_list = []
        if profile.interests:
            # Try comma-separated first, otherwise treat as single interest
            if "," in profile.interests:
                interests_list = [i.strip() for i in profile.interests.split(",") if i.strip()]
            else:
                interests_list = [profile.interests.strip()]
        
        # Generate user_id from email (simple hash or use email as ID)
        user_id = profile.email.split("@")[0]  # Use email prefix as user_id
        
        # Create user profile structure
        user_profile = {
            "user_id": user_id,
            "name": profile.name,
            "email": profile.email,
            "timezone": "UTC",  # Default, can be enhanced later
            "preferred_notification_times": notification_times,
            "content_preferences": interests_list,
        }
        
        # Check if user already exists in database
        try:
            existing_profile = get_user_profile_by_email(profile.email)
            
            if existing_profile:
                # User already registered
                return UserProfileResponse(
                    status="already_registered",
                    message=f"User {profile.name} ({profile.email}) has already been registered.",
                    user_id=existing_profile["user_id"],
                    profile=existing_profile
                )
            
            # User doesn't exist, save to database
            success = save_user_profile(user_profile)
            if not success:
                raise HTTPException(status_code=500, detail="Failed to save profile to database")
            
            return UserProfileResponse(
                status="success",
                message=f"Profile created successfully for {profile.name}",
                user_id=user_id,
                profile=user_profile
            )
            
        except NameError:
            # Database functions not available
            print("Warning: Database functions not available, profile not saved")
            return UserProfileResponse(
                status="warning",
                message=f"Profile created but not saved (database unavailable). User: {profile.name}",
                user_id=user_id,
                profile=user_profile
            )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creating profile: {str(e)}")

@app.post("/api/news/request", response_model=NewsRequestResponse)
async def request_news(request: NewsRequestRequest):
    """
    Request news based on user profile or custom query.
    
    If user_id is provided, uses stored profile preferences.
    If content_query is provided, uses that for news search.
    """
    try:
        # For now, use content_query if provided, otherwise default
        content_query = request.content_query or "today's key market and technology news"
        
        # Run news retrieval agent
        result = await retriv_run_agent(content_query)
        
        return NewsRequestResponse(
            status="success",
            content=result,
            message="News retrieved successfully"
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving news: {str(e)}")

@app.post("/api/personal-assistant/run")
async def run_personal_assistant_endpoint(profile: UserProfileRequest):
    """
    Run Personal Assistant Agent with user profile.
    This will gather news based on user preferences and schedule delivery.
    """
    try:
        # Parse notification times
        notification_times = []
        if profile.notification_time:
            times = [t.strip() for t in profile.notification_time.split(",") if t.strip()]
            notification_times = times
        
        # Parse interests
        interests_list = []
        if profile.interests:
            if "," in profile.interests:
                interests_list = [i.strip() for i in profile.interests.split(",") if i.strip()]
            else:
                interests_list = [profile.interests.strip()]
        
        # Create user profile
        user_profile = {
            "user_id": profile.email.split("@")[0],
            "name": profile.name,
            "email": profile.email,
            "timezone": "UTC",
            "preferred_notification_times": notification_times,
            "content_preferences": interests_list,
        }
        
        # Run personal assistant
        result = await run_personal_assistant(
            user_profile=user_profile,
            schedule_log=[],
            input_time=None,
            input_content="daily briefing based on user preferences",
            user_ip=None,
        )
        
        return {
            "status": "success",
            "result": result,
            "message": "Personal assistant completed successfully"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error running personal assistant: {str(e)}")

@app.get("/api/profile/{user_id}")
async def get_user_profile_endpoint(user_id: str):
    """Get user profile by user_id"""
    try:
        profile = get_user_profile(user_id)
        if profile:
            return {
                "status": "success",
                "profile": profile
            }
        else:
            raise HTTPException(status_code=404, detail=f"Profile not found for user_id: {user_id}")
    except NameError:
        raise HTTPException(status_code=503, detail="Database not available")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving profile: {str(e)}")

@app.get("/api/profile/email/{email}")
async def get_user_profile_by_email_endpoint(email: str):
    """Get user profile by email (GET endpoint)"""
    try:
        profile = get_user_profile_by_email(email)
        if profile:
            return {
                "status": "success",
                "profile": profile
            }
        else:
            raise HTTPException(status_code=404, detail=f"Profile not found for email: {email}")
    except NameError:
        raise HTTPException(status_code=503, detail="Database not available")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving profile: {str(e)}")

@app.post("/api/profile/check")
async def check_user_profile(request: CheckProfileRequest):
    """
    Check if a user profile exists by email.
    Returns the full profile if found.
    """
    try:
        profile = get_user_profile_by_email(request.email)
        if profile:
            return {
                "status": "found",
                "message": f"Profile found for {profile.get('name', 'User')}",
                "profile": profile
            }
        else:
            return {
                "status": "not_found",
                "message": f"No profile found for email: {request.email}",
                "profile": None
            }
    except NameError:
        raise HTTPException(status_code=503, detail="Database not available")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error checking profile: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8008)

