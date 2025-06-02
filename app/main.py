import os
import uuid
from fastapi import FastAPI, File, Form, UploadFile, Depends, HTTPException
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from azure.storage.blob import BlobServiceClient
from database import get_db, User
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = FastAPI(title="FastAPI Azure Demo", version="1.0.0")

# Azure Blob Storage configuration
AZURE_STORAGE_CONNECTION_STRING = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
CONTAINER_NAME = os.getenv("BLOB_CONTAINER_NAME", "images")

def get_blob_service_client():
    return BlobServiceClient.from_connection_string(AZURE_STORAGE_CONNECTION_STRING)

@app.get("/", response_class=HTMLResponse)
async def home():
    """Simple HTML form for testing"""
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>FastAPI Azure Demo</title>
        <style>
            body { font-family: Arial, sans-serif; max-width: 600px; margin: 50px auto; padding: 20px; }
            form { background: #f5f5f5; padding: 20px; border-radius: 8px; }
            input, textarea { width: 100%; padding: 10px; margin: 10px 0; border: 1px solid #ddd; border-radius: 4px; }
            button { background: #007bff; color: white; padding: 10px 20px; border: none; border-radius: 4px; cursor: pointer; }
            button:hover { background: #0056b3; }
        </style>
    </head>
    <body>
        <h1>User Registration</h1>
        <form action="/upload" method="post" enctype="multipart/form-data">
            <input type="text" name="user_id" placeholder="User ID" required>
            <input type="text" name="name" placeholder="Full Name" required>
            <textarea name="address" placeholder="Address" required></textarea>
            <input type="file" name="image" accept="image/*" required>
            <button type="submit">Submit</button>
        </form>
    </body>
    </html>
    """

@app.post("/upload")
async def upload_user_data(
    user_id: str = Form(...),
    name: str = Form(...),
    address: str = Form(...),
    image: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """Upload image to Azure Blob Storage and save user data to PostgreSQL"""
    
    try:
        # Validate image file
        if not image.content_type.startswith('image/'):
            raise HTTPException(status_code=400, detail="File must be an image")
        
        # Generate unique filename
        file_extension = image.filename.split('.')[-1]
        blob_name = f"{uuid.uuid4()}.{file_extension}"
        
        # Upload to Azure Blob Storage
        blob_service_client = get_blob_service_client()
        blob_client = blob_service_client.get_blob_client(
            container=CONTAINER_NAME, 
            blob=blob_name
        )
        
        # Upload file
        image_data = await image.read()
        blob_client.upload_blob(image_data, overwrite=True)
        
        # Get blob URL
        image_url = blob_client.url
        
        # Save to database
        db_user = User(
            user_id=user_id,
            name=name,
            address=address,
            image_url=image_url
        )
        db.add(db_user)
        db.commit()
        db.refresh(db_user)
        
        return {
            "message": "User data uploaded successfully",
            "user_id": user_id,
            "name": name,
            "address": address,
            "image_url": image_url,
            "database_id": db_user.id
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")

@app.get("/users")
async def get_users(db: Session = Depends(get_db)):
    """Get all users from database"""
    users = db.query(User).all()
    return {"users": users}

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)