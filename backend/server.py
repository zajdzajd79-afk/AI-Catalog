from fastapi import FastAPI, APIRouter, HTTPException
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field
from typing import List, Optional
import uuid
from datetime import datetime, timezone
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
    name: str  # required
    price: float  # required
    images: List[str] = Field(default_factory=list)  # base64 images, 1-5
    category: Optional[str] = None
    subcategory: Optional[str] = None
    barcode: Optional[str] = None
    article_number: Optional[str] = None
    # AI-extracted features for better matching
    ai_features: Optional[str] = None  # AI description of product features
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ProductCreate(BaseModel):
    name: str
    price: float
    images: List[str] = Field(..., min_length=1, max_length=5)
    category: Optional[str] = None
    subcategory: Optional[str] = None
    barcode: Optional[str] = None
    article_number: Optional[str] = None


class ProductUpdate(BaseModel):
    name: Optional[str] = None
    price: Optional[float] = None
    images: Optional[List[str]] = None
    category: Optional[str] = None
    subcategory: Optional[str] = None
    barcode: Optional[str] = None
    article_number: Optional[str] = None


class PhotoSearchRequest(BaseModel):
    image_base64: str


class SearchResponse(BaseModel):
    products: List[Product]
    confidence: Optional[str] = None
    ai_analysis: Optional[str] = None  # What AI saw in the image


# ============= AI Functions =============

async def extract_product_features(image_base64: str) -> str:
    """
    Extract distinctive product features from image using OpenAI Vision API.
    Focuses on the product itself, ignoring background.
    """
    try:
        api_key = os.environ.get('EMERGENT_LLM_KEY')
        chat = LlmChat(
            api_key=api_key,
            session_id=f"feature_extract_{uuid.uuid4()}",
            system_message="""You are an expert product analyzer. Your task is to extract distinctive features of products from images, focusing ONLY on the product itself and ignoring the background completely.

Focus on:
- Product type and shape
- Brand name and logos (if visible)
- Text on packaging (OCR)
- Colors and patterns of the product (not background)
- Distinctive design elements
- Barcode numbers visible on packaging
- Material and texture of the product

IGNORE completely:
- Background (carpet, table, floor, walls)
- Surrounding objects
- Lighting conditions
- Surface the product is placed on"""
        ).with_model("openai", "gpt-4o-mini")
        
        image_content = ImageContent(image_base64=image_base64)
        user_message = UserMessage(
            text="""Analyze ONLY the product in this image (ignore the background completely).

Extract and list:
1. PRODUCT TYPE: What kind of product is this?
2. BRAND/LOGO: Any brand names or logos visible on the product?
3. TEXT ON PACKAGING: All readable text on the product itself (use OCR)
4. COLORS: Main colors of the PRODUCT (not background)
5. SHAPE & FORM: Distinctive shape characteristics
6. PACKAGING DETAILS: Material, design patterns on the packaging
7. BARCODE: Any barcode numbers visible
8. UNIQUE FEATURES: Any distinctive elements that make this product unique

Be concise but thorough. Focus ONLY on the product, never the background.""",
            file_contents=[image_content]
        )
        
        response = await chat.send_message(user_message)
        return response.strip()
    except Exception as e:
        logging.error(f"Error extracting product features: {str(e)}")
        return ""


async def find_matching_product(query_image_base64: str, all_products: List[Product]) -> tuple:
    """
    Find matching product by comparing AI-extracted features.
    Returns (matched_product, ai_analysis) tuple.
    """
    try:
        if not all_products:
            return None, "No products in database"
        
        # Step 1: Extract features from query image
        query_features = await extract_product_features(query_image_base64)
        
        if not query_features:
            return None, "Could not analyze image"
        
        # Step 2: Build product catalog with their features for AI comparison
        product_catalog = []
        for i, p in enumerate(all_products):
            catalog_entry = f"#{i+1} - Name: {p.name}"
            if p.category:
                catalog_entry += f" | Category: {p.category}"
            if p.subcategory:
                catalog_entry += f" | Subcategory: {p.subcategory}"
            if p.barcode:
                catalog_entry += f" | Barcode: {p.barcode}"
            if p.article_number:
                catalog_entry += f" | Article: {p.article_number}"
            if p.ai_features:
                catalog_entry += f"\n   AI Features: {p.ai_features}"
            product_catalog.append(catalog_entry)
        
        catalog_text = "\n\n".join(product_catalog)
        
        # Step 3: Use AI to match the query against the catalog
        api_key = os.environ.get('EMERGENT_LLM_KEY')
        chat = LlmChat(
            api_key=api_key,
            session_id=f"product_match_{uuid.uuid4()}",
            system_message="""You are an expert product matching system. Your task is to find the best matching product from a catalog based on features extracted from a query image.

Focus ONLY on product-specific features:
- Product type and category
- Brand names and text on packaging
- Distinctive shape and colors OF THE PRODUCT
- Unique design elements

IGNORE:
- Background information
- Surface the product is placed on
- Lighting conditions"""
        ).with_model("openai", "gpt-4o-mini")
        
        image_content = ImageContent(image_base64=query_image_base64)
        user_message = UserMessage(
            text=f"""I have a product database. Find the BEST matching product for the image shown.

QUERY IMAGE FEATURES (extracted by AI, focused only on the product):
{query_features}

PRODUCT CATALOG:
{catalog_text}

INSTRUCTIONS:
1. Compare the query image features with each product in the catalog
2. Match based on PRODUCT characteristics (brand, type, shape, text on packaging)
3. IGNORE any background or environmental factors
4. If you find a confident match, respond with ONLY the product number (e.g., "3")
5. If no confident match exists, respond with "0"
6. Be strict - only match if you're confident it's the same product

Respond with ONLY a single number.""",
            file_contents=[image_content]
        )
        
        response = await chat.send_message(user_message)
        result = response.strip()
        
        # Extract number from response
        try:
            # Try to parse the number from response
            import re
            match = re.search(r'\d+', result)
            if match:
                match_index = int(match.group()) - 1
                if 0 <= match_index < len(all_products):
                    return all_products[match_index], query_features
        except Exception as e:
            logging.error(f"Error parsing match result: {e}")
            
        return None, query_features
        
    except Exception as e:
        logging.error(f"Error in product matching: {str(e)}")
        return None, str(e)


# ============= Helper Functions =============

def product_doc_to_model(doc: dict) -> dict:
    """Convert MongoDB document to Product model dict, handling legacy fields"""
    # Handle legacy image_base64 field (single image to list)
    if 'image_base64' in doc and 'images' not in doc:
        doc['images'] = [doc['image_base64']] if doc['image_base64'] else []
        del doc['image_base64']
    if '_id' in doc:
        del doc['_id']
    return doc


# ============= Category Routes =============

@api_router.get("/categories", response_model=List[Category])
async def get_categories():
    """Get all categories"""
    categories = await db.categories.find().to_list(1000)
    return [Category(**{k: v for k, v in c.items() if k != '_id'}) for c in categories] if categories else []


@api_router.post("/categories", response_model=Category)
async def create_category(category: Category):
    """Create a new category"""
    await db.categories.insert_one(category.dict())
    return category


# ============= Product Routes =============

@api_router.post("/products", response_model=Product)
async def create_product(product_data: ProductCreate):
    """Create a new product with AI feature extraction"""
    product = Product(**product_data.dict())
    
    # Extract AI features from the first image
    if product.images:
        ai_features = await extract_product_features(product.images[0])
        product.ai_features = ai_features
    
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
    return [Product(**product_doc_to_model(p)) for p in products]


@api_router.get("/products/{product_id}", response_model=Product)
async def get_product(product_id: str):
    """Get a single product by ID"""
    product = await db.products.find_one({"id": product_id})
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return Product(**product_doc_to_model(product))


@api_router.put("/products/{product_id}", response_model=Product)
async def update_product(product_id: str, product_data: ProductUpdate):
    """Update a product"""
    product = await db.products.find_one({"id": product_id})
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    
    update_data = {k: v for k, v in product_data.dict().items() if v is not None}
    update_data["updated_at"] = datetime.now(timezone.utc)
    
    # Re-extract AI features if images changed
    if 'images' in update_data and update_data['images']:
        ai_features = await extract_product_features(update_data['images'][0])
        update_data['ai_features'] = ai_features
    
    await db.products.update_one(
        {"id": product_id},
        {"$set": update_data}
    )
    
    updated_product = await db.products.find_one({"id": product_id})
    return Product(**product_doc_to_model(updated_product))


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
    """Search products by photo using AI with improved feature matching"""
    try:
        all_products_docs = await db.products.find().to_list(1000)
        if not all_products_docs:
            return SearchResponse(products=[], confidence="no_products")
        
        products_list = [Product(**product_doc_to_model(p)) for p in all_products_docs]
        
        matched_product, ai_analysis = await find_matching_product(request.image_base64, products_list)
        
        if matched_product:
            return SearchResponse(
                products=[matched_product],
                confidence="high",
                ai_analysis=ai_analysis
            )
        else:
            return SearchResponse(
                products=[],
                confidence="no_match",
                ai_analysis=ai_analysis
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
    return [Product(**product_doc_to_model(p)) for p in products]


@api_router.get("/products/search/barcode", response_model=Product)
async def search_by_barcode(barcode: str):
    """Search product by barcode"""
    product = await db.products.find_one({"barcode": barcode})
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return Product(**product_doc_to_model(product))


# ============= Root Routes =============

@api_router.get("/")
async def root():
    return {
        "message": "Smart AI Product Catalog API",
        "version": "2.0.0",
        "features": [
            "AI-powered product recognition with focus on product (not background)",
            "Multi-image support (1-5 images per product)",
            "Optional fields: category, subcategory, barcode, article",
            "OCR text recognition from packaging",
            "Brand and logo detection"
        ]
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
