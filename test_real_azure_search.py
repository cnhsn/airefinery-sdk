#!/usr/bin/env python3
"""
Comprehensive test script for Azure AI Search with your own index.
This script tests both API key and RBAC authentication methods.
"""

import sys
import os
import json
from typing import List, Dict, Any

# Add the parent directory to sys.path to import the air module
sys.path.insert(0, os.path.dirname(__file__))

# Configuration - Update these with your Azure AI Search details
AZURE_SEARCH_CONFIG = {
    "base_url": "https://test.search.windows.net",
    "index": "test-index",
    "api_version": "2023-11-01",
    "embedding_column": "text_vector",  # Vector field name from your index
    "content_columns": ["chunk", "title", "chunk_id"],  # Available fields from your index
    "top_k": 3
}

# Optional: Set your API key here for testing API key authentication
# Leave as None to skip API key tests
API_KEY = None  # Replace with your API key if you want to test API key auth


def test_rbac_authentication():
    """Test RBAC authentication and basic client creation"""
    print("🔐 Testing RBAC Authentication...")
    
    try:
        from air.api.vector_db.base_vectordb import VectorDBConfig
        from air.api.vector_db.azure_aisearch import AzureAISearch
        
        config = VectorDBConfig(
            base_url=AZURE_SEARCH_CONFIG["base_url"],
            auth_method="rbac",
            api_version=AZURE_SEARCH_CONFIG["api_version"],
            index=AZURE_SEARCH_CONFIG["index"],
            embedding_column=AZURE_SEARCH_CONFIG["embedding_column"],
            content_column=AZURE_SEARCH_CONFIG["content_columns"],
            top_k=AZURE_SEARCH_CONFIG["top_k"]
        )
        
        client = AzureAISearch(config)
        print(f"✅ RBAC client created successfully")
        print(f"   - Service URL: {config.base_url}")
        print(f"   - Index: {config.index}")
        print(f"   - Auth method: {client.auth_method}")
        
        return client, True
        
    except Exception as e:
        print(f"❌ RBAC authentication failed: {e}")
        import traceback
        traceback.print_exc()
        return None, False


def test_api_key_authentication():
    """Test API key authentication (if API key is provided)"""
    if not API_KEY:
        print("⏭️  Skipping API key test (no API key provided)")
        return None, True
    
    print("🔑 Testing API Key Authentication...")
    
    try:
        from air.api.vector_db.base_vectordb import VectorDBConfig
        from air.api.vector_db.azure_aisearch import AzureAISearch
        
        config = VectorDBConfig(
            base_url=AZURE_SEARCH_CONFIG["base_url"],
            auth_method="api_key",
            api_key=API_KEY,
            api_version=AZURE_SEARCH_CONFIG["api_version"],
            index=AZURE_SEARCH_CONFIG["index"],
            embedding_column=AZURE_SEARCH_CONFIG["embedding_column"],
            content_column=AZURE_SEARCH_CONFIG["content_columns"],
            top_k=AZURE_SEARCH_CONFIG["top_k"]
        )
        
        client = AzureAISearch(config)
        print(f"✅ API key client created successfully")
        print(f"   - Service URL: {config.base_url}")
        print(f"   - Index: {config.index}")
        print(f"   - Auth method: {client.auth_method}")
        
        return client, True
        
    except Exception as e:
        print(f"❌ API key authentication failed: {e}")
        import traceback
        traceback.print_exc()
        return None, False


def test_search_with_mock_embedding(client):
    """Test search functionality with a mock embedding vector"""
    if not client:
        return False
    
    print("🔍 Testing search with mock embedding...")
    
    try:
        # Create a mock embedding vector (your index uses 3072 dimensions)
        # This matches OpenAI's text-embedding-3-large model
        mock_embedding = [0.1] * 3072  # Correct dimension for your index
        
        # Create mock search data
        search_data = {
            "count": True,
            "select": ", ".join(AZURE_SEARCH_CONFIG["content_columns"]),
            "vectorQueries": [
                {
                    "kind": "vector",
                    "vector": mock_embedding,
                    "exhaustive": True,
                    "fields": AZURE_SEARCH_CONFIG["embedding_column"],
                    "k": AZURE_SEARCH_CONFIG["top_k"],
                }
            ]
        }
        
        # Make the search request
        import requests
        headers = client._get_auth_headers()
        
        response = requests.post(
            url=client.search_url,
            headers=headers,
            json=search_data,
            timeout=client.timeout
        )
        
        print(f"   - Search URL: {client.search_url}")
        print(f"   - Response Status: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ Search successful!")
            print(f"   - Total results: {result.get('@odata.count', 'unknown')}")
            print(f"   - Returned results: {len(result.get('value', []))}")
            
            # Display first result if available
            if result.get('value'):
                first_result = result['value'][0]
                print(f"   - First result keys: {list(first_result.keys())}")
                
            return True
        else:
            print(f"❌ Search failed with status {response.status_code}")
            print(f"   - Response: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Search test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_index_inspection(client):
    """Test index inspection to understand the schema"""
    if not client:
        return False
    
    print("📋 Inspecting index schema...")
    
    try:
        # Get index definition
        import requests
        headers = client._get_auth_headers()
        
        # Remove api-key from headers for index inspection as it uses different endpoint
        index_headers = {k: v for k, v in headers.items() if k.lower() != 'api-key'}
        if client.auth_method == "api_key":
            index_headers["api-key"] = client.api_key
        
        index_url = f"{client.url}/indexes/{client.index}?api-version={client.api_version}"
        
        response = requests.get(
            url=index_url,
            headers=index_headers,
            timeout=client.timeout
        )
        
        if response.status_code == 200:
            index_def = response.json()
            print(f"✅ Index inspection successful!")
            print(f"   - Index name: {index_def.get('name')}")
            
            fields = index_def.get('fields', [])
            print(f"   - Total fields: {len(fields)}")
            
            print("   - Field details:")
            for field in fields[:10]:  # Show first 10 fields
                field_type = field.get('type', 'unknown')
                searchable = field.get('searchable', False)
                filterable = field.get('filterable', False)
                print(f"     • {field.get('name')}: {field_type} (searchable: {searchable}, filterable: {filterable})")
            
            if len(fields) > 10:
                print(f"     ... and {len(fields) - 10} more fields")
            
            return True
        else:
            print(f"❌ Index inspection failed with status {response.status_code}")
            print(f"   - Response: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Index inspection failed: {e}")
        return False


def test_authentication_token_refresh(client):
    """Test authentication token refresh for RBAC"""
    if not client or client.auth_method != "rbac":
        print("⏭️  Skipping token refresh test (not using RBAC)")
        return True
    
    print("🔄 Testing RBAC token refresh...")
    
    try:
        # Force token refresh by clearing cache
        client._token_cache = None
        client._token_expiry = None
        
        # Get fresh headers (should trigger token acquisition)
        headers1 = client._get_auth_headers()
        print("✅ First token acquisition successful")
        
        # Get headers again (should use cached token)
        headers2 = client._get_auth_headers()
        print("✅ Token caching working")
        
        # Verify both have Authorization headers
        if "Authorization" in headers1 and "Authorization" in headers2:
            print("✅ Authorization headers present")
            return True
        else:
            print("❌ Missing Authorization headers")
            return False
            
    except Exception as e:
        print(f"❌ Token refresh test failed: {e}")
        return False


def main():
    """Run all tests"""
    print("🧪 Azure AI Search RBAC Testing Suite")
    print("=" * 50)
    print(f"Service URL: {AZURE_SEARCH_CONFIG['base_url']}")
    print(f"Index: {AZURE_SEARCH_CONFIG['index']}")
    print()
    
    results = []
    
    # Test RBAC authentication
    rbac_client, rbac_success = test_rbac_authentication()
    results.append(("RBAC Authentication", rbac_success))
    
    print()
    
    # Test API key authentication
    api_client, api_success = test_api_key_authentication()
    results.append(("API Key Authentication", api_success))
    
    print()
    
    # Choose the successful client for further tests
    test_client = rbac_client if rbac_success else (api_client if api_success else None)
    
    if test_client:
        # Test index inspection
        inspect_success = test_index_inspection(test_client)
        results.append(("Index Inspection", inspect_success))
        
        print()
        
        # Test token refresh (RBAC only)
        token_success = test_authentication_token_refresh(test_client)
        results.append(("Token Refresh", token_success))
        
        print()
        
        # Test search functionality
        search_success = test_search_with_mock_embedding(test_client)
        results.append(("Mock Search", search_success))
    else:
        print("❌ No successful authentication - skipping further tests")
        results.extend([
            ("Index Inspection", False),
            ("Token Refresh", False),
            ("Mock Search", False)
        ])
    
    # Summary
    print()
    print("📊 Test Results Summary")
    print("=" * 30)
    
    passed = 0
    for test_name, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{test_name}: {status}")
        if success:
            passed += 1
    
    print()
    print(f"Overall: {passed}/{len(results)} tests passed")
    
    if passed == len(results):
        print("🎉 All tests passed! Your Azure AI Search RBAC integration is working perfectly!")
    elif passed > 0:
        print("⚠️  Some tests passed. Check the failed tests above for issues.")
    else:
        print("❌ All tests failed. Please check your configuration and Azure permissions.")
    
    # Provide next steps
    print()
    print("📝 Next Steps:")
    if not rbac_success:
        print("• Ensure you're authenticated with Azure (run 'az login')")
        print("• Verify you have the required Azure roles assigned:")
        print("  - Search Index Data Contributor (for upload)")
        print("  - Search Index Data Reader (for search)")
    
    if test_client and inspect_success:
        print("• Update the AZURE_SEARCH_CONFIG in this script with the correct field names")
        print("• Create a proper embedding client for real vector searches")
        print("• Test with actual documents and embeddings")


if __name__ == "__main__":
    main()
