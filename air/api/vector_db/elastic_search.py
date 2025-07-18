"""Elastic Search implementation of the VectorDB interface."""

import json
import logging
from typing import List

import requests
from requests.exceptions import HTTPError
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_random_exponential,
)

from air import auth
from air.api.vector_db.base_vectordb import BaseVectorDB, VectorDBConfig
from air.embeddings import EmbeddingsClient

logger = logging.getLogger(__name__)


class ElasticSearch(BaseVectorDB):
    """
    A class to interact with the ElasticSearch API for vector-based retrieval.

    This class uses embeddings generated by the embed_api client to perform vector
    searches on an ElasticSearch index, returning relevant documents based on
    the user’s query.
    """

    def __init__(self, vectordb_config: VectorDBConfig):
        super().__init__(vectordb_config)
        self.fields = vectordb_config.embedding_column
        self.k = vectordb_config.top_k
        self.select = vectordb_config.content_column
        self.timeout = vectordb_config.timeout
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"ApiKey {vectordb_config.api_key}",
        }
        self.search_url = f"{self.url}/{self.index}/_search"
        self.index_url = f"{self.url}/{self.index}/_bulk"

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
            bulk_lines = ""
            for row in rows:
                action = (
                    {"index": {"_id": row["_id"]}}
                    if row.get("_id", None)
                    else {"index": {}}
                )
                bulk_lines += f"{json.dumps(action)}\n{json.dumps(row)}\n"
            response = requests.post(
                self.index_url,
                headers=self.headers,
                data=bulk_lines.encode("utf-8"),
                timeout=self.timeout,
            )
            response.raise_for_status()
            res_json = response.json()
            if res_json.get("errors"):
                logger.error("One or more documents failed to index.")
                return False
            return True
        except HTTPError as http_err:
            logger.error(
                "VectorDB upload request failed due to HTTP error: %s", http_err
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
            payload = {
                "knn": {
                    "field": self.fields,
                    "k": self.k,
                    "num_candidates": 100,
                    "query_vector": vector,  # .tolist(),
                },
                "_source": self.select,
            }
            response = requests.post(
                self.search_url,
                headers=self.headers,
                json=payload,
                timeout=self.timeout,
            )
            response.raise_for_status()
            response = response.json()
            hits = response.get("hits", {}).get("hits", [])
            flattened = [hit["_source"] for hit in hits]

            return flattened
        except HTTPError as http_err:
            logger.error(
                "Elastic Search DB search request failed due to HTTP error: %s",
                http_err,
            )
            logger.error("Failed to retrieve from Elastic search API")
            return []
