"""Backend API tests for Smart AI Product Catalog."""
import base64
import io
import os
import uuid
import time

import pytest
import requests
from PIL import Image

from conftest import BASE_URL


# ===== Helpers =====

def _png_base64(color=(255, 0, 0), size=(64, 64)) -> str:
    img = Image.new("RGB", size, color=color)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("utf-8")


@pytest.fixture(scope="module")
def created_ids():
    return {"products": [], "categories": []}


# ===== Health / Root =====

class TestRoot:
    def test_root_endpoint(self, api_client):
        r = api_client.get(f"{BASE_URL}/api/")
        assert r.status_code == 200, r.text
        data = r.json()
        assert "message" in data
        assert "endpoints" in data


# ===== Categories =====

class TestCategories:
    def test_get_categories_empty_or_list(self, api_client):
        r = api_client.get(f"{BASE_URL}/api/categories")
        assert r.status_code == 200, r.text
        assert isinstance(r.json(), list)

    def test_create_and_get_category(self, api_client, created_ids):
        payload = {
            "name": f"TEST_Cat_{uuid.uuid4().hex[:6]}",
            "subcategories": ["sub1", "sub2"],
        }
        r = api_client.post(f"{BASE_URL}/api/categories", json=payload)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["name"] == payload["name"]
        assert data["subcategories"] == payload["subcategories"]
        assert "id" in data
        created_ids["categories"].append(data["id"])

        # Verify persisted
        r2 = api_client.get(f"{BASE_URL}/api/categories")
        assert r2.status_code == 200
        names = [c["name"] for c in r2.json()]
        assert payload["name"] in names


# ===== Products CRUD =====

class TestProducts:
    def test_create_product(self, api_client, created_ids):
        payload = {
            "name": f"TEST_Product_{uuid.uuid4().hex[:6]}",
            "category": "Beverages",
            "subcategory": "Soda",
            "barcode": f"TEST-BC-{uuid.uuid4().hex[:8]}",
            "article_number": f"ART-{uuid.uuid4().hex[:6]}",
            "price": 9.99,
            "image_base64": _png_base64((255, 0, 0)),
        }
        r = api_client.post(f"{BASE_URL}/api/products", json=payload)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["name"] == payload["name"]
        assert data["barcode"] == payload["barcode"]
        assert data["price"] == 9.99
        assert "id" in data
        created_ids["products"].append(data["id"])
        created_ids["last_barcode"] = payload["barcode"]
        created_ids["last_name"] = payload["name"]

    def test_get_product_by_id(self, api_client, created_ids):
        assert created_ids["products"], "Need a created product"
        pid = created_ids["products"][0]
        r = api_client.get(f"{BASE_URL}/api/products/{pid}")
        assert r.status_code == 200, r.text
        assert r.json()["id"] == pid

    def test_get_product_not_found(self, api_client):
        r = api_client.get(f"{BASE_URL}/api/products/non-existent-id-xyz")
        assert r.status_code == 404

    def test_list_products(self, api_client, created_ids):
        r = api_client.get(f"{BASE_URL}/api/products")
        assert r.status_code == 200, r.text
        data = r.json()
        assert isinstance(data, list)
        ids = [p["id"] for p in data]
        assert created_ids["products"][0] in ids

    def test_list_products_filter_category(self, api_client):
        r = api_client.get(f"{BASE_URL}/api/products", params={"category": "Beverages"})
        assert r.status_code == 200
        for p in r.json():
            assert p["category"] == "Beverages"

    def test_update_product(self, api_client, created_ids):
        pid = created_ids["products"][0]
        new_price = 19.99
        r = api_client.put(
            f"{BASE_URL}/api/products/{pid}",
            json={"price": new_price, "name": "TEST_Updated_Name"},
        )
        assert r.status_code == 200, r.text
        assert r.json()["price"] == new_price
        # Verify via GET
        r2 = api_client.get(f"{BASE_URL}/api/products/{pid}")
        assert r2.json()["price"] == new_price
        assert r2.json()["name"] == "TEST_Updated_Name"

    def test_update_product_not_found(self, api_client):
        r = api_client.put(
            f"{BASE_URL}/api/products/non-existent",
            json={"price": 1.0},
        )
        assert r.status_code == 404


# ===== Search =====

class TestSearch:
    def test_text_search(self, api_client, created_ids):
        # name was updated to TEST_Updated_Name
        r = api_client.get(f"{BASE_URL}/api/products/search/text", params={"q": "TEST_Updated"})
        assert r.status_code == 200, r.text
        data = r.json()
        assert isinstance(data, list)
        assert any(p["id"] == created_ids["products"][0] for p in data)

    def test_barcode_search(self, api_client, created_ids):
        bc = created_ids["last_barcode"]
        r = api_client.get(f"{BASE_URL}/api/products/search/barcode", params={"barcode": bc})
        assert r.status_code == 200, r.text
        assert r.json()["barcode"] == bc

    def test_barcode_search_not_found(self, api_client):
        r = api_client.get(
            f"{BASE_URL}/api/products/search/barcode",
            params={"barcode": "DOES-NOT-EXIST-9999"},
        )
        assert r.status_code == 404

    def test_photo_search_returns_200(self, api_client):
        """Critical: previously returned 500 due to missing await. Should now return 200."""
        img_b64 = _png_base64((0, 255, 0))
        r = api_client.post(
            f"{BASE_URL}/api/products/search/photo",
            json={"image_base64": img_b64},
            timeout=60,
        )
        assert r.status_code == 200, f"Photo search failed: {r.status_code} - {r.text}"
        data = r.json()
        assert "products" in data
        assert "confidence" in data
        assert isinstance(data["products"], list)
        # confidence is one of: high, no_match, no_products
        assert data["confidence"] in ("high", "no_match", "no_products")


# ===== Cleanup =====

class TestZCleanup:
    def test_delete_created_products(self, api_client, created_ids):
        for pid in created_ids["products"]:
            r = api_client.delete(f"{BASE_URL}/api/products/{pid}")
            assert r.status_code == 200, r.text
            # Confirm 404 on GET
            g = api_client.get(f"{BASE_URL}/api/products/{pid}")
            assert g.status_code == 404

    def test_delete_product_not_found(self, api_client):
        r = api_client.delete(f"{BASE_URL}/api/products/non-existent")
        assert r.status_code == 404
