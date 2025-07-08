"""
Azure AI Search module, supports upload and vector search with API key and RBAC authentication
"""

import json
import logging
from typing import List, Optional

import requests
from requests.exceptions import HTTPError
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_random_exponential,
)

try:
    from azure.identity import DefaultAzureCredential
    from azure.core.credentials import AccessToken
    AZURE_IDENTITY_AVAILABLE = True
except ImportError:
    AZURE_IDENTITY_AVAILABLE = False
    DefaultAzureCredential = None
    AccessToken = None

from air import auth
from air.api.vector_db.base_vectordb import BaseVectorDB, VectorDBConfig
from air.embeddings import EmbeddingsClient

logger = logging.getLogger(__name__)


class AzureAISearch(BaseVectorDB):
    """
    Class to upload data to vector DB, inherits from BaseVectorDB.
    Supports both API key and Azure RBAC authentication.
    """

    def __init__(self, vectordb_config: VectorDBConfig):
        super().__init__(vectordb_config)
        self.fields = vectordb_config.embedding_column
        self.k = vectordb_config.top_k
        self.select = ", ".join(vectordb_config.content_column)
        self.timeout = vectordb_config.timeout
        
        # Initialize authentication
        self._init_authentication()
        
        self.search_url = f"{self.url}/indexes/{self.index}/docs/search?api-version={self.api_version}"
        self.index_url = (
            f"{self.url}/indexes/{self.index}/docs/index?api-version={self.api_version}"
        )

    def _init_authentication(self):
        """Initialize authentication based on the configured method"""
        if self.auth_method == "api_key":
            if not self.api_key:
                raise ValueError("API key is required for API key authentication")
            self.headers = {"Content-Type": "application/json", "api-key": self.api_key}
            self.credential = None
        elif self.auth_method == "rbac":
            if not AZURE_IDENTITY_AVAILABLE:
                raise ImportError(
                    "azure-identity package is required for RBAC authentication. "
                    "Install it with: pip install azure-identity"
                )
            self.credential = DefaultAzureCredential()
            self.headers = {"Content-Type": "application/json"}
            self._token_cache = None
            self._token_expiry = None
        else:
            raise ValueError(f"Unsupported authentication method: {self.auth_method}")

    def _get_auth_headers(self) -> dict:
        """Get authentication headers based on the configured method"""
        if self.auth_method == "api_key":
            return self.headers
        elif self.auth_method == "rbac":
            return self._get_rbac_headers()

    def _get_rbac_headers(self) -> dict:
        """Get headers with Azure RBAC Bearer token"""
        import time
        
        # Check if we need to refresh the token
        current_time = time.time()
        if (self._token_cache is None or 
            self._token_expiry is None or 
            current_time >= self._token_expiry - 300):  # Refresh 5 minutes before expiry
            
            try:
                # Azure Cognitive Search scope for RBAC
                token = self.credential.get_token("https://search.azure.com/.default")
                self._token_cache = token.token
                self._token_expiry = token.expires_on
                logger.debug("Successfully obtained Azure RBAC token for Azure AI Search")
            except Exception as e:
                logger.error(f"Failed to obtain Azure RBAC token: {e}")
                raise RuntimeError(f"Failed to authenticate with Azure RBAC: {e}")
        
        headers = self.headers.copy()
        headers["Authorization"] = f"Bearer {self._token_cache}"
        return headers

    @retry(
        retry=retry_if_exception_type(requests.exceptions.HTTPError),
        stop=stop_after_attempt(5),
        wait=wait_random_exponential(multiplier=2, min=2, max=6),
    )
    def upload(self, rows: List[dict]) -> bool:
        """
        Function to upload list of document data to vector DB

        Args:
            rows (List[dict]): List of row dictionaries to be uploaded to the vector DB

        Returns:
            bool: Status of vector DB upload, False if failure, True if success
        """
        try:
            rows = [dict(row, **{"@search.action": "upload"}) for row in rows]
            data = {"value": rows}
            headers = self._get_auth_headers()
            response = requests.post(
                self.index_url, headers=headers, json=data, timeout=self.timeout
            )
            response.raise_for_status()
            return True
        except HTTPError as http_err:
            logger.error(
                "VectorDB upload request failed due to HTTP error: %s", http_err
            )
            return False
        except Exception as e:
            logger.error(
                "VectorDB upload request failed due to error: %s", e
            )
            return False

    @retry(
        retry=retry_if_exception_type(requests.exceptions.HTTPError),
        stop=stop_after_attempt(5),
        wait=wait_random_exponential(multiplier=2, min=2, max=6),
    )
    def vector_search(
        self, query: str, embedding_client: EmbeddingsClient, embedding_model: str
    ) -> List[dict]:
        """
        Function to perform vector search over the index
        using the given query.

        Args:
            query (str): Query string which will be used to
            create a search vector to search over the vector DB index

        Returns:
            List[dict]: List of k vector db row dictionaries
            that were retrieved by the vector search
        """
        try:
            vector = (
                embedding_client.create(
                    input=[query],
                    model=embedding_model,
                    encoding_format="float",
                    extra_body={"input_type": "query"},
                    extra_headers={"airefinery_account": auth.account},
                )
                .data[0]
                .embedding
            )
        except HTTPError as http_err:
            logger.error(
                "Embedding generation request failed due to HTTP error: %s",
                http_err,
            )
            return []
        if not vector:
            logger.error("Embedding client did not return a response for the query.")
            return []

        try:
            search_vectors = [
                {
                    "kind": "vector",
                    "vector": vector,
                    "exhaustive": True,
                    "fields": self.fields,
                    "k": self.k,
                }
            ]
            data = {
                "count": True,
                "select": self.select,
                "vectorQueries": search_vectors,
            }
            headers = self._get_auth_headers()
            response = requests.post(
                url=self.search_url,
                headers=headers,
                json=data,
                timeout=self.timeout,
            )
            response.raise_for_status()
            response = json.loads(response.text)
            result = response["value"]
            return result
        except HTTPError as http_err:
            logger.error(
                "Azure AI Search DB search request failed due to HTTP error: %s",
                http_err,
            )
            logger.error("Failed to retrieve from Azure AI search API")
            return []
        except Exception as e:
            logger.error(
                "Azure AI Search DB search request failed due to error: %s", e
            )
            return []
