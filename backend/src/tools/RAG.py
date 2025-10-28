from livekit.agents import function_tool
from typing import List
import aiohttp
import asyncio
import logging

RAG_API_URL = "https://ml.demisco.ai/api/chat/" 

logger = logging.getLogger("RAG")

@function_tool
async def search_and_respond(query: str, knowledge_base_ids:  List[str] = ["76eb9478-0bbe-4116-952e-51c0c541f0b4"]) -> str:
    """
    Search the knowledge base and answer questions about Demis products, medical reference systems,
    invoicing, features, documentation, or any company-specific information.
    
    Use this tool whenever a user asks about:
    - Medical reference systems or invoicing
    - Demis products or features  
    - Company documentation or procedures
    - Any specific information not in your general knowledge
    
    Args:
        query: The user's question to search for.
        knowledge_base_ids: List of knowledge base UUIDs to search.
    """

    payload = {"query": query, "knowledge_store_uuids": knowledge_base_ids}

    try:
        # Call the RAG API to get the full prompt
        async with aiohttp.ClientSession() as session:
            async with session.post(RAG_API_URL, json=payload, timeout=10) as response:
                if response.status != 200:
                    error_detail = await response.text()
                    logger.error(f"[RAG] API error {response.status}: {error_detail}")
                    return "I had trouble accessing my knowledge base right now. Please try again."
                
                # Get the complete prompt from RAG API
                response_data = await response.json()
                
                rag_prompt = response_data.get("text")

                if not rag_prompt:
                    logger.error(f"[RAG] API response missing 'prompt' key.")
                    return "I found some information, but had trouble processing it."

        logger.info("[RAG] Received full prompt from RAG API.")
        
        # Return the RAG prompt for the agent to use
        return rag_prompt
    
    except asyncio.TimeoutError:
        logger.error(f"[RAG] Timeout while calling RAG API")
        return "The knowledge base took too long to respond. Please try again."
    except Exception as e:
        logger.error(f"[RAG] Unexpected error in search_and_respond: {e}", exc_info=True)
        return "I ran into an unexpected error while looking that up."