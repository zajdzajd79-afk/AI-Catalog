# Smart AI Product Catalog v2.0 - PRD

## Overview
AI-powered mobile application for product recognition and catalog management. Users can identify products by taking photos, scanning barcodes, or text search. AI focuses on PRODUCT features, not background.

## Tech Stack
- **Frontend**: Expo (React Native) with expo-router
- **Backend**: FastAPI (Python)
- **Database**: MongoDB
- **AI**: OpenAI Vision API (gpt-4o-mini) via emergentintegrations library
- **Camera**: expo-camera with built-in barcode scanner
- **Language**: Russian (all UI text)

## v2.0 Major Updates

### 🎯 Critical AI Improvements
**Problem solved**: AI was recognizing background instead of product
**Solution**: Two-stage AI matching:
1. **Feature extraction** - AI analyzes ONLY the product (type, brand, OCR text, colors, distinctive features) and IGNORES background
2. **Smart matching** - AI compares extracted features against catalog with strict matching rules

The AI now:
- ✅ Extracts text via OCR from product packaging
- ✅ Detects brand names and logos
- ✅ Focuses on product shape, packaging, distinctive features
- ❌ IGNORES carpet, table, background completely
- ❌ IGNORES lighting and surface where product placed

### 📸 Multi-Image Support
- 1 photo minimum (required)
- Up to 5 photos per product
- First photo marked as "Главное" (main)
- Image carousel in product details
- AI feature extraction from primary image

### 📋 Optional Fields
**Required**: name, price, ≥1 image
**Optional**: barcode, article_number, category, subcategory

### 📊 Barcode Scanner (NEW)
- Built-in camera barcode scanner (expo-camera)
- Supports: EAN-13, EAN-8, UPC-A, UPC-E, Code128, Code39, QR, etc.
- **Two modes**:
  - Search mode: scan → find product → show details
  - Capture mode: scan → return barcode to add/edit form
- Manual barcode input modal as fallback
- Accessible from home, catalog, and add/edit screens

## App Screens
1. `/` - Home (4 gradient action cards)
2. `/camera` - AI Photo Search camera interface
3. `/barcode-scanner` - Barcode scanner (modes: search/capture)
4. `/catalog` - Products list with text search + barcode shortcut
5. `/add-product` - Add new product (multi-photo + scanner integration)
6. `/edit-product` - Edit product (same features as add)
7. `/product-detail` - Product details with image carousel + AI features

## Backend API Endpoints
- `GET /api/` - Health check
- `POST /api/products` - Create product (validates 1-5 images, runs AI extraction)
- `GET /api/products` - List all products (with category/subcategory filters)
- `GET /api/products/{id}` - Get single product
- `PUT /api/products/{id}` - Update product (re-runs AI if images changed)
- `DELETE /api/products/{id}` - Delete product
- `POST /api/products/search/photo` - AI photo search (returns ai_analysis)
- `GET /api/products/search/text?q=` - Text search
- `GET /api/products/search/barcode?barcode=` - Barcode search
- `GET /api/categories` - List categories
- `POST /api/categories` - Create category

## Data Models

### Product
- id (UUID)
- name (str, required)
- price (float, required)
- images (List[str], 1-5 required) - base64 images
- category (Optional[str])
- subcategory (Optional[str])
- barcode (Optional[str])
- article_number (Optional[str])
- ai_features (Optional[str]) - AI-extracted product description
- created_at, updated_at (datetime, timezone-aware UTC)

### SearchResponse
- products (List[Product])
- confidence (str) - "high", "no_match", "no_products"
- ai_analysis (str) - AI's analysis of the query image

### Legacy compatibility
- Old products with `image_base64` (single image) automatically migrated to `images` array on read

## Design System
- **Primary color**: #667eea (purple-blue)
- **Accent colors**:
  - Photo Search: #667eea → #764ba2 (purple gradient)
  - Barcode Scanner: #fa709a → #fee140 (pink-yellow gradient)
  - Catalog: #f093fb → #f5576c (pink gradient)
  - Add Product: #4facfe → #00f2fe (blue gradient)
- **Background**: #f8f9fa
- **Text**: #1a1a1a
- **Secondary**: #6c757d

## Permissions (app.json)
- iOS: NSCameraUsageDescription, NSPhotoLibraryUsageDescription
- Android: CAMERA, READ/WRITE_EXTERNAL_STORAGE
- Properly configured plugins for expo-camera and expo-image-picker

## Testing Status
- ✅ Backend: 22/22 tests passed including AI feature extraction
- ✅ Multi-image upload and validation
- ✅ Optional fields work correctly
- ✅ AI photo search with real OpenAI Vision (~5-10s per call)
- ✅ Legacy data migration
- ✅ Barcode search with 404 handling

## Future Enhancements
- OCR via dedicated EasyOCR/Tesseract (currently via Vision API)
- Multi-product detection (shelf recognition)
- Local embeddings with CLIP + FAISS for offline mode
- User accounts and favorites
- Search history
- Dark mode
- Multi-language support (KZ/EN)
- Bulk import via CSV

## Native Build Note
Camera barcode scanning works best in development build. In Expo Go basic camera works but scanner performance may vary. For production, build via Emergent publish button.
