# Azure AI Search RBAC Authentication

This document describes how to use Azure AI Search with Role-Based Access Control (RBAC) authentication instead of API keys.

## Overview

The Azure AI Search integration in the AI Refinery SDK now supports two authentication methods:

1. **API Key Authentication** (existing method) - Uses API keys for authentication
2. **RBAC Authentication** (new method) - Uses Azure Active Directory (AAD) identity and role-based access control

## Authentication Methods

### API Key Authentication (Default)

This is the traditional method using API keys:

```python
from air.api.vector_db.base_vectordb import VectorDBConfig
from air.api.vector_db.azure_aisearch import AzureAISearch

config = VectorDBConfig(
    type="AzureAISearch",
    base_url="https://your-search-service.search.windows.net",
    api_key="your-api-key-here",
    auth_method="api_key",  # This is the default
    index="your-index-name",
    embedding_column="text_vector",
    content_column=["content", "title"]
)

search_client = AzureAISearch(config)
```

### RBAC Authentication (New)

This method uses Azure Identity and doesn't require API keys:

```python
from air.api.vector_db.base_vectordb import VectorDBConfig
from air.api.vector_db.azure_aisearch import AzureAISearch

config = VectorDBConfig(
    type="AzureAISearch",
    base_url="https://your-search-service.search.windows.net",
    auth_method="rbac",  # Use RBAC authentication
    index="your-index-name",
    embedding_column="text_vector",
    content_column=["content", "title"]
    # Note: No api_key needed
)

search_client = AzureAISearch(config)
```

## Prerequisites for RBAC Authentication

### 1. Azure Roles

Your Azure identity must have the appropriate roles assigned:

- **Search Index Data Contributor** - Required for uploading/indexing documents
- **Search Index Data Reader** - Required for searching documents  
- **Search Service Contributor** - Required for managing the search service (optional)

### 2. Authentication Setup

Configure authentication using one of these methods:

#### Azure CLI (for local development)
```bash
az login
```

#### Service Principal (for production)
Set these environment variables:
```bash
export AZURE_CLIENT_ID="your-client-id"
export AZURE_CLIENT_SECRET="your-client-secret"
export AZURE_TENANT_ID="your-tenant-id"
```

#### Managed Identity (for Azure resources)
No additional setup needed when running on Azure resources with managed identity enabled.

#### Visual Studio/VS Code
Sign in to your Azure account through the IDE.

### 3. Dependencies

The SDK already includes the required `azure-identity` package. If you need to install it separately:

```bash
pip install azure-identity
```

## Configuration Options

### VectorDBConfig Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `auth_method` | `str` | `"api_key"` | Authentication method: `"api_key"` or `"rbac"` |
| `api_key` | `str` | `None` | API key (required for `api_key` auth, ignored for `rbac`) |
| `base_url` | `str` | Required | Azure Search service URL |
| `index` | `str` | Required | Index name |
| `embedding_column` | `str` | `"text_vector"` | Column name for embeddings |
| `content_column` | `List[str]` | `[]` | Columns to return in search results |
| `top_k` | `int` | `1` | Number of top results to return |
| `timeout` | `int` | `60` | Request timeout in seconds |

## Security Benefits of RBAC

1. **Enhanced Security**: No API keys to manage or accidentally expose
2. **Fine-grained Access Control**: Precise role-based permissions
3. **Centralized Identity Management**: Integrated with Azure Active Directory
4. **Audit Trail**: All operations are logged with the authenticated identity
5. **Token Rotation**: Automatic token refresh and expiration handling

## Error Handling

The implementation includes comprehensive error handling:

```python
try:
    search_client = AzureAISearch(config)
    results = search_client.vector_search(query, embedding_client, model)
except ValueError as e:
    print(f"Configuration error: {e}")
except RuntimeError as e:
    print(f"Authentication error: {e}")
except Exception as e:
    print(f"Unexpected error: {e}")
```

## Migration from API Key to RBAC

To migrate from API key authentication to RBAC:

1. **Set up Azure roles** for your identity
2. **Update your configuration**:
   ```python
   # Before (API Key)
   config = VectorDBConfig(
       base_url="https://your-service.search.windows.net",
       api_key="your-api-key",
       auth_method="api_key",
       # ... other params
   )
   
   # After (RBAC)
   config = VectorDBConfig(
       base_url="https://your-service.search.windows.net",
       auth_method="rbac",
       # ... other params (remove api_key)
   )
   ```
3. **Test the configuration** before deploying to production
4. **Remove API keys** from your Azure Search service once RBAC is working

## Troubleshooting

### Common Issues

1. **"Failed to authenticate with Azure RBAC"**
   - Verify your Azure identity is properly configured
   - Check that you have the required roles assigned
   - Ensure you're logged in (for local development)

2. **"azure-identity package is required"**
   - Install the azure-identity package: `pip install azure-identity`

3. **Permission denied errors**
   - Verify you have the correct Azure roles assigned
   - Check the scope of your role assignment

4. **Token refresh issues**
   - The implementation automatically handles token refresh
   - Check network connectivity to Azure endpoints

### Debug Logging

Enable debug logging to troubleshoot authentication issues:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## Example: Complete RBAC Workflow

See `examples/azure_aisearch_rbac_example.py` for a complete example demonstrating:
- Configuration setup
- Document uploading
- Vector search
- Error handling

## Best Practices

1. **Use RBAC in production** for enhanced security
2. **Assign minimal required roles** (principle of least privilege)
3. **Monitor authentication logs** for security auditing
4. **Test thoroughly** before migrating from API keys
5. **Use managed identity** when running on Azure resources
