from fastapi import FastAPI, APIRouter, HTTPException, File, UploadFile
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field
from typing import List, Optional
import uuid
from datetime import datetime
import base64
from io import BytesIO
from PIL import Image
from emergentintegrations.llm.chat import LlmChat, UserMessage, ImageContent


ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# Create the main app without a prefix
app = FastAPI()

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")


# ============= Models =============

class Category(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    subcategories: List[str] = []

class Product(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    category: str
    subcategory: str
    barcode: str
    article_number: str
    price: float
    image_base64: str  # Store image as base64
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class ProductCreate(BaseModel):
    name: str
    category: str
    subcategory: str
    barcode: str
    article_number: str
    price: float
    image_base64: str

class ProductUpdate(BaseModel):
    name: Optional[str] = None
    category: Optional[str] = None
    subcategory: Optional[str] = None
    barcode: Optional[str] = None
    article_number: Optional[str] = None
    price: Optional[float] = None
    image_base64: Optional[str] = None

class PhotoSearchRequest(BaseModel):
    image_base64: str

class SearchResponse(BaseModel):
    products: List[Product]
    confidence: Optional[str] = None


# ============= AI Functions =============

async def analyze_product_image(image_base64: str, all_products: List[Product]) -> Optional[Product]:
    """
    Analyze product image using OpenAI Vision API and find matching product
    """
    try:
        # Create product descriptions for matching
        product_descriptions = []
        for p in all_products:
            desc = f"Product: {p.name}, Category: {p.category}, Subcategory: {p.subcategory}, Barcode: {p.barcode}"
            product_descriptions.append(desc)
        
        products_text = "\n".join([f"{i+1}. {desc}" for i, desc in enumerate(product_descriptions)])
        
        # Initialize LlmChat with emergentintegrations
        api_key = os.environ.get('EMERGENT_LLM_KEY', os.environ.get('OPENAI_API_KEY'))
        chat = LlmChat(
            api_key=api_key,
            session_id=f"product_search_{uuid.uuid4()}",
            system_message="You are a product identification assistant."
        ).with_model("openai", "gpt-4o-mini")
        
        # Create image content
        image_content = ImageContent(image_base64=image_base64)
        
        # Create user message with image
        user_message = UserMessage(
            text=f"""Analyze this product image and find the best matching product from the list below.
            
Products in database:
{products_text}

Please respond with ONLY the number of the matching product (1-{len(all_products)}). If no good match exists, respond with '0'.
Consider the visual appearance, category, and type of product.""",
            file_contents=[image_content]
        )
        
        # Send message and get response
        response = await chat.send_message(user_message)
        
        # Extract number from response
        try:
            match_index = int(response.strip()) - 1
            if 0 <= match_index < len(all_products):
                return all_products[match_index]
        except:
            pass
            
        return None
        
    except Exception as e:
        logging.error(f"Error in AI analysis: {str(e)}")
        return None


# ============= Category Routes =============

@api_router.get("/categories", response_model=List[Category])
async def get_categories():
    """Get all categories"""
    categories = await db.categories.find().to_list(1000)
    return [Category(**c) for c in categories] if categories else []

@api_router.post("/categories")
async def create_category(category: Category):
    """Create a new category"""
    await db.categories.insert_one(category.dict())
    return category


# ============= Product Routes =============

@api_router.post("/products", response_model=Product)
async def create_product(product_data: ProductCreate):
    """Create a new product"""
    product = Product(**product_data.dict())
    await db.products.insert_one(product.dict())
    return product

@api_router.get("/products", response_model=List[Product])
async def get_products(
    category: Optional[str] = None,
    subcategory: Optional[str] = None
):
    """Get all products with optional filtering"""
    query = {}
    if category:
        query["category"] = category
    if subcategory:
        query["subcategory"] = subcategory
    
    products = await db.products.find(query).to_list(1000)
    return [Product(**p) for p in products]

@api_router.get("/products/{product_id}", response_model=Product)
async def get_product(product_id: str):
    """Get a single product by ID"""
    product = await db.products.find_one({"id": product_id})
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return Product(**product)

@api_router.put("/products/{product_id}", response_model=Product)
async def update_product(product_id: str, product_data: ProductUpdate):
    """Update a product"""
    product = await db.products.find_one({"id": product_id})
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    
    update_data = {k: v for k, v in product_data.dict().items() if v is not None}
    update_data["updated_at"] = datetime.utcnow()
    
    await db.products.update_one(
        {"id": product_id},
        {"$set": update_data}
    )
    
    updated_product = await db.products.find_one({"id": product_id})
    return Product(**updated_product)

@api_router.delete("/products/{product_id}")
async def delete_product(product_id: str):
    """Delete a product"""
    result = await db.products.delete_one({"id": product_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Product not found")
    return {"message": "Product deleted successfully"}


# ============= Search Routes =============

@api_router.post("/products/search/photo", response_model=SearchResponse)
async def search_by_photo(request: PhotoSearchRequest):
    """Search products by photo using AI"""
    try:
        # Get all products
        all_products = await db.products.find().to_list(1000)
        if not all_products:
            return SearchResponse(products=[], confidence="no_products")
        
        products_list = [Product(**p) for p in all_products]
        
        # Use AI to find matching product
        matched_product = await analyze_product_image(request.image_base64, products_list)
        
        if matched_product:
            return SearchResponse(
                products=[matched_product],
                confidence="high"
            )
        else:
            return SearchResponse(
                products=[],
                confidence="no_match"
            )
            
    except Exception as e:
        logging.error(f"Error in photo search: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/products/search/text", response_model=List[Product])
async def search_by_text(q: str):
    """Search products by name"""
    products = await db.products.find({
        "name": {"$regex": q, "$options": "i"}
    }).to_list(1000)
    return [Product(**p) for p in products]

@api_router.get("/products/search/barcode", response_model=Product)
async def search_by_barcode(barcode: str):
    """Search product by barcode"""
    product = await db.products.find_one({"barcode": barcode})
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return Product(**product)


# ============= Root Routes =============

@api_router.get("/")
async def root():
    return {
        "message": "Smart AI Product Catalog API",
        "version": "1.0.0",
        "endpoints": {
            "products": "/api/products",
            "categories": "/api/categories",
            "search_photo": "/api/products/search/photo",
            "search_text": "/api/products/search/text",
            "search_barcode": "/api/products/search/barcode"
        }
    }


# Include the router in the main app
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
