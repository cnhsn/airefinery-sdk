"""
Base module for Vector DB, supports upload and search
"""

import logging
from abc import ABCMeta
from typing import List, Optional, Literal, Union

from pydantic import BaseModel, Field, model_validator

from air.api.vector_db.vectordb_registry import VectorDBRegistry

logger = logging.getLogger(__name__)


class VectorDBConfig(BaseModel):
    """
    VectorDB configuration class
    """

    type: str = Field(default="AzureAISearch", description="Type of the Vector DB")
    base_url: str = Field(..., description="Vector DB URL")
    api_key: Union[str, None] = Field(default=None, description="API key required to access the vector DB (for API key authentication)")
    auth_method: Literal["api_key", "rbac"] = Field(default="api_key", description="Authentication method: 'api_key' for API key authentication or 'rbac' for Azure RBAC authentication")
    api_version: str = Field(default="2023-11-01", description="API Version")
    index: str = Field(..., description="Name of the vector db index")
    embedding_column: str = Field(
        default="text_vector",
        description="Name of the column in the vector db that stores embeddings for vector searches",
    )
    top_k: int = Field(
        default=1,
        description="Number of top results (k) to return from each vector search request",
    )
    content_column: List[str] = Field(
        default=[],
        description="List of columns from which content should be returned in search results",
    )
    timeout: int = Field(default=60, description="Vector DB POST request timeout")

    @model_validator(mode='after')
    def validate_auth_config(self):
        """Validate that the authentication configuration is correct"""
        if self.auth_method == "api_key" and self.api_key is None:
            raise ValueError("api_key is required when auth_method is 'api_key'")
        if self.auth_method == "rbac" and self.api_key is not None:
            logger.warning("api_key is ignored when auth_method is 'rbac'")
        return self


class VectorDBMeta(ABCMeta):
    """
    A metaclass that registers any concrete subclass of BaseVectorDB
    in VectorDBRegistry at creation time.

    Because BaseVectorDB already depends on ABC (which uses ABCMeta),
    we must inherit from ABCMeta here to avoid a metaclass conflict.
    """

    def __init__(cls, name, bases, namespace):
        super().__init__(name, bases, namespace)

        # Avoid registering the abstract base itself or any other classes
        # that are still abstract (i.e., if they haven't implemented all
        # abstract methods).
        if cls.__name__ != "BaseVectorDB" and not getattr(
            cls, "__abstractmethods__", False
        ):
            VectorDBRegistry.register(cls)


class BaseVectorDB(metaclass=VectorDBMeta):
    """
    Base configuration class for any vector DB
    """

    def __init__(self, vectordb_config: VectorDBConfig):
        self.url = vectordb_config.base_url
        self.api_key = vectordb_config.api_key
        self.auth_method = vectordb_config.auth_method
        self.api_version = vectordb_config.api_version
        self.index = vectordb_config.index
