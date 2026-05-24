# Smart AI Product Catalog - PRD

## Overview
AI-powered mobile application for product recognition and catalog management. Users can identify products by taking photos, and the AI matches them with the database.

## Tech Stack
- **Frontend**: Expo (React Native) with expo-router
- **Backend**: FastAPI (Python)
- **Database**: MongoDB
- **AI**: OpenAI Vision API (gpt-4o-mini) via emergentintegrations library
- **Language**: Russian (all UI text)

## MVP Features Implemented

### 1. AI Photo Search (Main Feature)
- User takes a photo with camera or selects from gallery
- AI analyzes the image using OpenAI Vision API
- Returns the best matching product from database
- Shows product details: name, category, price, barcode, article number

### 2. Product Catalog
- Grid/list view of all products
- Search by product name (text search)
- Real-time filtering
- Empty state with helpful messages

### 3. Add Product
- Form with all required fields
- Image upload (camera or gallery)
- Categories and subcategories (free-text)
- Barcode and article number
- Price input

### 4. Edit & Delete Product
- Edit all product fields
- Replace product image
- Delete with confirmation

### 5. Product Details
- Beautiful detail screen with hero image
- Gradient overlay
- All product info in cards with colored icons
- Edit/Delete actions

## App Screens
1. `/` - Home (3 gradient action cards)
2. `/camera` - AI Photo Search camera interface
3. `/catalog` - Products list with search
4. `/add-product` - Add new product form
5. `/edit-product` - Edit product form
6. `/product-detail` - Product details view

## Backend API Endpoints
- `GET /api/` - Health check
- `POST /api/products` - Create product
- `GET /api/products` - List all products (with category/subcategory filters)
- `GET /api/products/{id}` - Get single product
- `PUT /api/products/{id}` - Update product
- `DELETE /api/products/{id}` - Delete product
- `POST /api/products/search/photo` - AI photo search
- `GET /api/products/search/text?q=` - Text search
- `GET /api/products/search/barcode?barcode=` - Barcode search
- `GET /api/categories` - List categories
- `POST /api/categories` - Create category

## Data Models

### Product
- id (UUID)
- name (str)
- category (str)
- subcategory (str)
- barcode (str)
- article_number (str)
- price (float)
- image_base64 (str)
- created_at, updated_at (datetime)

### Category
- id (UUID)
- name (str)
- subcategories (List[str])

## Design System
- **Primary color**: #667eea (purple-blue)
- **Accent colors**: 
  - Photo Search: #667eea → #764ba2 (purple gradient)
  - Catalog: #f093fb → #f5576c (pink gradient)
  - Add Product: #4facfe → #00f2fe (blue gradient)
- **Background**: #f8f9fa (light gray)
- **Text**: #1a1a1a (almost black)
- **Secondary**: #6c757d (gray)

## Future Enhancements (Not in MVP)
- OCR text recognition from packaging
- Built-in barcode scanner
- Multiple product detection (shelf recognition)
- Offline mode with sync
- User accounts and favorites
- Search history
- Dark mode
- Multi-language support (EN/KZ)
- Local CLIP model + FAISS for offline search

## Native Build Note
The camera and image picker features work in Expo Go for basic testing. For production deployment, a development/production build is recommended for best camera performance.
