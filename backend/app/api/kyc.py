"""
ChainForensics - KYC Privacy Check API
Endpoints for analyzing privacy of KYC exchange withdrawals.
"""
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.core.kyc_trace import get_kyc_tracer, KYCPrivacyTracer

logger = logging.getLogger("chainforensics.api.kyc")

router = APIRouter()


class KYCTraceRequest(BaseModel):
    """Request model for KYC privacy trace."""
    exchange_txid: str = Field(..., description="Transaction ID of the exchange withdrawal")
    destination_address: str = Field(..., description="Address that received the withdrawal")
    depth_preset: str = Field("standard", description="Depth preset: quick, standard, deep, or thorough")


@router.get("/presets")
async def get_depth_presets():
    """
    Get available depth presets for KYC privacy tracing.
    
    Returns the available scan depth options with descriptions.
    """
    return {
        "presets": KYCPrivacyTracer.DEPTH_PRESETS,
        "default": "standard",
        "description": "Choose a depth preset based on how thorough you want the analysis"
    }


@router.post("/trace")
async def trace_kyc_withdrawal(request: KYCTraceRequest):
    """
    Trace a KYC exchange withdrawal to analyze privacy.
    
    This endpoint helps you understand what an adversary who knows your
    exchange withdrawal details could potentially discover about your
    current Bitcoin holdings.
    
    **Input:**
    - `exchange_txid`: The transaction ID from your exchange withdrawal
    - `destination_address`: The address you withdrew to
    - `depth_preset`: How deep to search (quick/standard/deep/thorough)
    
    **Output:**
    - List of probable current destinations with confidence scores
    - Overall privacy score (0-100, higher = more private)
    - Recommendations for improving privacy
    """
    tracer = get_kyc_tracer()
    
    # Validate depth preset
    if request.depth_preset not in KYCPrivacyTracer.DEPTH_PRESETS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid depth preset. Choose from: {list(KYCPrivacyTracer.DEPTH_PRESETS.keys())}"
        )
    
    try:
        result = await tracer.trace_kyc_withdrawal(
            exchange_txid=request.exchange_txid,
            destination_address=request.destination_address,
            depth_preset=request.depth_preset
        )
        
        return result.to_dict()
        
    except Exception as e:
        logger.error(f"KYC trace error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/trace")
async def trace_kyc_withdrawal_get(
    exchange_txid: str = Query(..., description="Transaction ID of the exchange withdrawal"),
    destination_address: str = Query(..., description="Address that received the withdrawal"),
    depth_preset: str = Query("standard", description="Depth preset: quick, standard, deep, thorough")
):
    """
    Trace a KYC exchange withdrawal to analyze privacy (GET version).
    
    Same as POST /trace but using query parameters for easier testing.
    """
    tracer = get_kyc_tracer()
    
    # Validate depth preset
    if depth_preset not in KYCPrivacyTracer.DEPTH_PRESETS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid depth preset. Choose from: {list(KYCPrivacyTracer.DEPTH_PRESETS.keys())}"
        )
    
    try:
        result = await tracer.trace_kyc_withdrawal(
            exchange_txid=exchange_txid,
            destination_address=destination_address,
            depth_preset=depth_preset
        )
        
        return result.to_dict()
        
    except Exception as e:
        logger.error(f"KYC trace error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/quick-check")
async def quick_privacy_check(
    exchange_txid: str = Query(..., description="Transaction ID of the exchange withdrawal"),
    destination_address: str = Query(..., description="Address that received the withdrawal")
):
    """
    Quick privacy check with minimal depth.
    
    Use this for a fast initial assessment. For thorough analysis, use /trace.
    """
    tracer = get_kyc_tracer()
    
    try:
        result = await tracer.trace_kyc_withdrawal(
            exchange_txid=exchange_txid,
            destination_address=destination_address,
            depth_preset="quick"
        )
        
        # Return simplified result
        return {
            "privacy_score": result.overall_privacy_score,
            "privacy_rating": result.privacy_rating,
            "summary": result.summary,
            "high_confidence_destinations": result.to_dict()["high_confidence_destinations"],
            "coinjoins_encountered": result.coinjoins_encountered,
            "recommendations": result.recommendations[:3] if result.recommendations else [],
            "full_analysis_available": True,
            "message": "Use /trace endpoint with higher depth for detailed analysis"
        }
        
    except Exception as e:
        logger.error(f"Quick check error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
