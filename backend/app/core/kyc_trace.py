"""
ChainForensics - KYC Privacy Trace Module
Analyzes if funds from a known KYC withdrawal can be traced to current holdings.

This module helps users check their own privacy by simulating what an
adversary who knows their exchange withdrawal details could discover.
"""
import asyncio
import logging
from datetime import datetime
from typing import Dict, List, Optional, Set, Tuple
from dataclasses import dataclass, field
from enum import Enum
from collections import Counter

from app.config import settings
from app.core.bitcoin_rpc import BitcoinRPC, get_rpc

logger = logging.getLogger("chainforensics.kyc_trace")


class TrailStatus(Enum):
    """Status of a trace trail."""
    ACTIVE = "active"           # Trail is clear and traceable
    COLD = "cold"               # Trail went through CoinJoin (2nd one = stop)
    DEAD_END = "dead_end"       # Trail hit an unspent UTXO
    DEPTH_LIMIT = "depth_limit" # Hit max depth
    LOST = "lost"               # Cannot follow (no electrs, etc)


class ConfidenceLevel(Enum):
    """Confidence levels for attribution."""
    HIGH = "high"       # 70-100% - Very likely same owner
    MEDIUM = "medium"   # 40-69% - Possibly same owner
    LOW = "low"         # 20-39% - Unlikely same owner
    NEGLIGIBLE = "negligible"  # <20% - Almost certainly not traceable


@dataclass
class PathNode:
    """A node in the trace path."""
    txid: str
    vout: int
    value_sats: int
    address: Optional[str]
    block_height: Optional[int]
    block_time: Optional[datetime]
    is_coinjoin: bool
    coinjoin_score: float
    coinjoin_count_in_path: int  # How many CoinJoins we've passed through
    depth: int
    is_change: bool = False
    change_probability: float = 0.0
    
    @property
    def value_btc(self) -> float:
        return self.value_sats / 100_000_000
    
    def to_dict(self) -> Dict:
        return {
            "txid": self.txid,
            "vout": self.vout,
            "value_sats": self.value_sats,
            "value_btc": self.value_btc,
            "address": self.address,
            "block_height": self.block_height,
            "block_time": self.block_time.isoformat() if self.block_time else None,
            "is_coinjoin": self.is_coinjoin,
            "coinjoin_score": self.coinjoin_score,
            "coinjoin_count_in_path": self.coinjoin_count_in_path,
            "depth": self.depth,
            "is_change": self.is_change,
            "change_probability": self.change_probability
        }


@dataclass
class ProbableDestination:
    """A probable final destination for the traced funds."""
    address: str
    value_sats: int
    confidence_score: float  # 0.0 to 1.0
    confidence_level: ConfidenceLevel
    path_length: int
    coinjoins_passed: int
    trail_status: TrailStatus
    reasoning: List[str]
    path: List[PathNode]
    
    @property
    def value_btc(self) -> float:
        return self.value_sats / 100_000_000
    
    def to_dict(self) -> Dict:
        return {
            "address": self.address,
            "value_sats": self.value_sats,
            "value_btc": self.value_btc,
            "confidence_score": round(self.confidence_score * 100, 1),
            "confidence_level": self.confidence_level.value,
            "confidence_percent": f"{self.confidence_score * 100:.1f}%",
            "path_length": self.path_length,
            "coinjoins_passed": self.coinjoins_passed,
            "trail_status": self.trail_status.value,
            "reasoning": self.reasoning,
            "path": [n.to_dict() for n in self.path]
        }


@dataclass
class KYCTraceResult:
    """Complete result of a KYC privacy trace."""
    exchange_txid: str
    destination_address: str
    original_value_sats: int
    trace_depth: int
    
    # Results
    probable_destinations: List[ProbableDestination] = field(default_factory=list)
    total_traced_sats: int = 0
    total_untraceable_sats: int = 0
    coinjoins_encountered: int = 0
    
    # Analysis
    overall_privacy_score: float = 0.0  # 0-100, higher = more private
    privacy_rating: str = "unknown"
    summary: str = ""
    warnings: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    
    # Metadata
    execution_time_ms: int = 0
    electrs_enabled: bool = False
    
    @property
    def original_value_btc(self) -> float:
        return self.original_value_sats / 100_000_000
    
    def to_dict(self) -> Dict:
        return {
            "exchange_txid": self.exchange_txid,
            "destination_address": self.destination_address,
            "original_value_sats": self.original_value_sats,
            "original_value_btc": self.original_value_btc,
            "trace_depth": self.trace_depth,
            "probable_destinations": [d.to_dict() for d in self.probable_destinations],
            "total_traced_sats": self.total_traced_sats,
            "total_traced_btc": self.total_traced_sats / 100_000_000,
            "total_untraceable_sats": self.total_untraceable_sats,
            "total_untraceable_btc": self.total_untraceable_sats / 100_000_000,
            "untraceable_percent": round(self.total_untraceable_sats / max(self.original_value_sats, 1) * 100, 1),
            "coinjoins_encountered": self.coinjoins_encountered,
            "overall_privacy_score": round(self.overall_privacy_score, 1),
            "privacy_rating": self.privacy_rating,
            "summary": self.summary,
            "warnings": self.warnings,
            "recommendations": self.recommendations,
            "execution_time_ms": self.execution_time_ms,
            "electrs_enabled": self.electrs_enabled,
            "destination_count": len(self.probable_destinations),
            "high_confidence_destinations": len([d for d in self.probable_destinations if d.confidence_level == ConfidenceLevel.HIGH]),
            "medium_confidence_destinations": len([d for d in self.probable_destinations if d.confidence_level == ConfidenceLevel.MEDIUM])
        }


class KYCPrivacyTracer:
    """
    Traces funds from a known KYC exchange withdrawal to probable current holdings.
    
    This helps users understand what an adversary with knowledge of their
    exchange withdrawal could potentially discover about their current holdings.
    """
    
    # Depth presets with complexity descriptions
    DEPTH_PRESETS = {
        "quick": {
            "depth": 3,
            "label": "Quick Scan",
            "description": "Fast check, 1-3 hops only",
            "complexity": "Low"
        },
        "standard": {
            "depth": 6,
            "label": "Standard",
            "description": "Balanced depth, covers most patterns",
            "complexity": "Medium"
        },
        "deep": {
            "depth": 10,
            "label": "Deep Scan",
            "description": "Thorough analysis, may take longer",
            "complexity": "High"
        },
        "thorough": {
            "depth": 15,
            "label": "Thorough",
            "description": "Very deep analysis, intensive",
            "complexity": "Very High"
        }
    }
    
    MAX_DEPTH = 15  # Absolute maximum
    MAX_TRANSACTIONS = 300
    MAX_QUEUE_SIZE = 1000
    COINJOIN_THRESHOLD = 0.7  # Score above this = CoinJoin
    MAX_COINJOINS_BEFORE_COLD = 2  # Stop tracing after 2nd CoinJoin
    
    def __init__(self, rpc: BitcoinRPC = None):
        self.rpc = rpc or get_rpc()
        self._tx_cache: Dict[str, Dict] = {}
        self._electrs = None
        self._electrs_checked = False
    
    async def _get_electrs(self):
        """Lazy load Electrs client."""
        if not self._electrs_checked:
            try:
                from app.core.electrs import get_electrs
                self._electrs = get_electrs()
                if self._electrs.is_configured:
                    await self._electrs.connect()
                else:
                    self._electrs = None
            except Exception as e:
                logger.debug(f"Electrs not available: {e}")
                self._electrs = None
            self._electrs_checked = True
        return self._electrs
    
    async def _get_transaction(self, txid: str) -> Optional[Dict]:
        """Get transaction with caching."""
        if txid in self._tx_cache:
            return self._tx_cache[txid]
        
        try:
            tx = await self.rpc.get_raw_transaction(txid, True)
            if tx:
                self._tx_cache[txid] = tx
            return tx
        except Exception as e:
            logger.warning(f"Failed to fetch transaction {txid}: {e}")
            return None
    
    def _calculate_coinjoin_score(self, tx: Dict) -> float:
        """Calculate CoinJoin probability score."""
        vouts = tx.get("vout", [])
        vins = tx.get("vin", [])
        
        if len(vouts) < 2:
            return 0.0
        
        values = [round(out.get("value", 0), 8) for out in vouts]
        value_counts = Counter(values)
        
        if not value_counts:
            return 0.0
        
        max_equal = max(value_counts.values())
        num_outputs = len(vouts)
        num_inputs = len(vins)
        
        # Whirlpool: exactly 5 equal outputs
        if num_outputs == 5 and max_equal == 5:
            return 0.95
        
        # Wasabi: many equal outputs
        if max_equal >= 10:
            return 0.90
        
        # JoinMarket / Generic
        if max_equal >= 5 and num_inputs >= 3:
            return 0.75
        
        if max_equal >= 3 and num_inputs >= 2:
            return 0.50
        
        return 0.0
    
    def _detect_change_output(
        self,
        tx: Dict,
        input_addresses: Set[str],
        output_idx: int,
        original_value: int
    ) -> Tuple[bool, float]:
        """
        Detect if an output is likely change.
        
        Returns (is_change, probability)
        """
        vouts = tx.get("vout", [])
        if output_idx >= len(vouts):
            return False, 0.0
        
        output = vouts[output_idx]
        output_value = int(output.get("value", 0) * 100_000_000)
        output_script = output.get("scriptPubKey", {})
        output_address = output_script.get("address")
        output_type = output_script.get("type", "")
        
        probability = 0.0
        
        # Heuristic 1: Address reuse (sending back to input address)
        if output_address and output_address in input_addresses:
            probability += 0.4
        
        # Heuristic 2: Same script type as inputs
        input_types = set()
        for vin in tx.get("vin", []):
            if "prevout" in vin:
                input_types.add(vin["prevout"].get("scriptPubKey", {}).get("type", ""))
        
        if output_type in input_types:
            probability += 0.1
        
        # Heuristic 3: Non-round number (change is often "weird" amounts)
        value_btc = output_value / 100_000_000
        # Check if it's a round number
        is_round = (value_btc * 1000) % 1 == 0  # Multiple of 0.001
        if not is_round:
            probability += 0.15
        
        # Heuristic 4: Smaller than largest output (often payment is larger)
        max_output = max(int(v.get("value", 0) * 100_000_000) for v in vouts)
        if output_value < max_output:
            probability += 0.1
        
        # Heuristic 5: Position (change often last, but not always)
        if output_idx == len(vouts) - 1:
            probability += 0.05
        
        return probability > 0.3, min(probability, 0.95)
    
    def _calculate_path_confidence(
        self,
        path: List[PathNode],
        original_value: int
    ) -> Tuple[float, List[str]]:
        """
        Calculate confidence score for a traced path.
        
        Returns (confidence_score, reasoning_list)
        """
        if not path:
            return 0.0, ["Empty path"]
        
        reasoning = []
        confidence = 1.0
        
        # Factor 1: Path length (longer = less confident)
        path_length = len(path)
        if path_length == 1:
            reasoning.append("Direct transfer (1 hop)")
        elif path_length <= 3:
            confidence *= 0.9
            reasoning.append(f"Short path ({path_length} hops)")
        elif path_length <= 6:
            confidence *= 0.7
            reasoning.append(f"Medium path ({path_length} hops)")
        else:
            confidence *= 0.5
            reasoning.append(f"Long path ({path_length} hops)")
        
        # Factor 2: CoinJoins in path
        coinjoins = sum(1 for n in path if n.is_coinjoin)
        if coinjoins == 0:
            reasoning.append("No CoinJoins in path")
        elif coinjoins == 1:
            confidence *= 0.4
            reasoning.append("Passed through 1 CoinJoin (reduced confidence)")
        else:
            confidence *= 0.1
            reasoning.append(f"Passed through {coinjoins} CoinJoins (trail very cold)")
        
        # Factor 3: Value similarity to original
        if path:
            final_value = path[-1].value_sats
            value_ratio = final_value / max(original_value, 1)
            
            if value_ratio > 0.9:
                reasoning.append("Value very similar to original (>90%)")
            elif value_ratio > 0.5:
                confidence *= 0.8
                reasoning.append(f"Value is {value_ratio*100:.0f}% of original")
            elif value_ratio > 0.1:
                confidence *= 0.6
                reasoning.append(f"Value is {value_ratio*100:.0f}% of original (likely split)")
            else:
                confidence *= 0.4
                reasoning.append(f"Value is only {value_ratio*100:.1f}% of original")
        
        # Factor 4: Change detection in path
        change_nodes = [n for n in path if n.is_change]
        if change_nodes:
            avg_change_prob = sum(n.change_probability for n in change_nodes) / len(change_nodes)
            confidence *= (0.7 + 0.3 * avg_change_prob)
            reasoning.append(f"Path follows likely change outputs ({len(change_nodes)} nodes)")
        
        return min(max(confidence, 0.0), 1.0), reasoning
    
    def _get_confidence_level(self, score: float) -> ConfidenceLevel:
        """Convert score to confidence level."""
        if score >= 0.7:
            return ConfidenceLevel.HIGH
        elif score >= 0.4:
            return ConfidenceLevel.MEDIUM
        elif score >= 0.2:
            return ConfidenceLevel.LOW
        else:
            return ConfidenceLevel.NEGLIGIBLE
    
    async def _find_spending_tx(self, txid: str, vout: int, address: str) -> Optional[str]:
        """Find transaction that spent a specific output using Electrs."""
        electrs = await self._get_electrs()
        if not electrs:
            return None
        
        try:
            history = await electrs.get_history(address)
            
            for hist_tx in history:
                if hist_tx.txid == txid:
                    continue
                
                try:
                    full_tx = await self._get_transaction(hist_tx.txid)
                    if not full_tx:
                        continue
                    
                    for vin in full_tx.get("vin", []):
                        if vin.get("txid") == txid and vin.get("vout") == vout:
                            return hist_tx.txid
                except Exception:
                    continue
            
            return None
        except Exception as e:
            logger.debug(f"Error finding spending tx: {e}")
            return None
    
    async def trace_kyc_withdrawal(
        self,
        exchange_txid: str,
        destination_address: str,
        depth_preset: str = "standard"
    ) -> KYCTraceResult:
        """
        Trace a KYC exchange withdrawal to find probable current holdings.
        
        Args:
            exchange_txid: Transaction ID of the exchange withdrawal
            destination_address: Address that received the withdrawal
            depth_preset: One of "quick", "standard", "deep", "thorough"
        
        Returns:
            KYCTraceResult with probable destinations and privacy analysis
        """
        start_time = datetime.utcnow()
        
        # Get depth from preset
        preset = self.DEPTH_PRESETS.get(depth_preset, self.DEPTH_PRESETS["standard"])
        max_depth = min(preset["depth"], self.MAX_DEPTH)
        
        result = KYCTraceResult(
            exchange_txid=exchange_txid,
            destination_address=destination_address,
            original_value_sats=0,
            trace_depth=max_depth
        )
        
        # Check Electrs availability
        electrs = await self._get_electrs()
        result.electrs_enabled = electrs is not None
        
        if not electrs:
            result.warnings.append("Electrs not available - forward tracing will be limited")
        
        # Get the initial transaction
        tx = await self._get_transaction(exchange_txid)
        if not tx:
            result.warnings.append(f"Transaction not found: {exchange_txid}")
            result.summary = "Could not find the exchange transaction"
            return result
        
        # Find the output that went to destination_address
        start_vout = None
        start_value = 0
        
        for idx, vout in enumerate(tx.get("vout", [])):
            script = vout.get("scriptPubKey", {})
            addr = script.get("address")
            if addr == destination_address:
                start_vout = idx
                start_value = int(vout.get("value", 0) * 100_000_000)
                break
        
        if start_vout is None:
            result.warnings.append(f"Destination address {destination_address} not found in transaction outputs")
            result.summary = "The destination address was not found in the transaction"
            return result
        
        result.original_value_sats = start_value
        
        # BFS to trace funds forward
        # Queue: (txid, vout, depth, coinjoin_count, path, current_value)
        queue: List[Tuple[str, int, int, int, List[PathNode], int]] = [
            (exchange_txid, start_vout, 0, 0, [], start_value)
        ]
        
        visited: Set[Tuple[str, int]] = set()
        destinations: List[ProbableDestination] = []
        tx_count = 0
        coinjoin_txids: Set[str] = set()
        
        while queue and tx_count < self.MAX_TRANSACTIONS:
            if len(queue) > self.MAX_QUEUE_SIZE:
                result.warnings.append("Queue size exceeded, some paths truncated")
                queue = queue[:self.MAX_QUEUE_SIZE]
            
            current_txid, current_vout, depth, cj_count, path, tracked_value = queue.pop(0)
            
            if (current_txid, current_vout) in visited:
                continue
            visited.add((current_txid, current_vout))
            
            # Depth limit check
            if depth > max_depth:
                # Add as destination with depth limit status
                if path:
                    conf_score, reasoning = self._calculate_path_confidence(path, start_value)
                    reasoning.append("Hit depth limit")
                    destinations.append(ProbableDestination(
                        address=path[-1].address or "unknown",
                        value_sats=tracked_value,
                        confidence_score=conf_score * 0.5,  # Reduce confidence at limit
                        confidence_level=self._get_confidence_level(conf_score * 0.5),
                        path_length=len(path),
                        coinjoins_passed=cj_count,
                        trail_status=TrailStatus.DEPTH_LIMIT,
                        reasoning=reasoning,
                        path=path
                    ))
                continue
            
            # Get transaction
            tx = await self._get_transaction(current_txid)
            if not tx:
                continue
            
            tx_count += 1
            
            # Get output info
            vouts = tx.get("vout", [])
            if current_vout >= len(vouts):
                continue
            
            output = vouts[current_vout]
            value_sats = int(output.get("value", 0) * 100_000_000)
            script = output.get("scriptPubKey", {})
            address = script.get("address")
            script_type = script.get("type", "unknown")
            
            block_height = tx.get("blockheight") or tx.get("height")
            block_time = None
            if tx.get("blocktime"):
                block_time = datetime.utcfromtimestamp(tx["blocktime"])
            
            # Check if this is a CoinJoin
            cj_score = self._calculate_coinjoin_score(tx)
            is_coinjoin = cj_score >= self.COINJOIN_THRESHOLD
            
            current_cj_count = cj_count
            if is_coinjoin:
                current_cj_count += 1
                coinjoin_txids.add(current_txid)
            
            # Get input addresses for change detection
            input_addresses: Set[str] = set()
            for vin in tx.get("vin", []):
                if "prevout" in vin:
                    addr = vin["prevout"].get("scriptPubKey", {}).get("address")
                    if addr:
                        input_addresses.add(addr)
            
            # Detect change
            is_change, change_prob = self._detect_change_output(
                tx, input_addresses, current_vout, tracked_value
            )
            
            # Create path node
            node = PathNode(
                txid=current_txid,
                vout=current_vout,
                value_sats=value_sats,
                address=address,
                block_height=block_height,
                block_time=block_time,
                is_coinjoin=is_coinjoin,
                coinjoin_score=cj_score,
                coinjoin_count_in_path=current_cj_count,
                depth=depth,
                is_change=is_change,
                change_probability=change_prob
            )
            
            current_path = path + [node]
            
            # Check if we should stop (2nd CoinJoin = trail cold)
            if current_cj_count >= self.MAX_COINJOINS_BEFORE_COLD:
                conf_score, reasoning = self._calculate_path_confidence(current_path, start_value)
                reasoning.append(f"Trail went cold after {current_cj_count} CoinJoins")
                
                destinations.append(ProbableDestination(
                    address=address or "unknown",
                    value_sats=value_sats,
                    confidence_score=conf_score,
                    confidence_level=self._get_confidence_level(conf_score),
                    path_length=len(current_path),
                    coinjoins_passed=current_cj_count,
                    trail_status=TrailStatus.COLD,
                    reasoning=reasoning,
                    path=current_path
                ))
                result.total_untraceable_sats += value_sats
                continue
            
            # Check if UTXO is unspent
            utxo_status = await self.rpc.get_tx_out(current_txid, current_vout)
            
            if utxo_status:
                # Unspent - this is a destination
                conf_score, reasoning = self._calculate_path_confidence(current_path, start_value)
                reasoning.append("UTXO is unspent (current holding)")
                
                destinations.append(ProbableDestination(
                    address=address or "unknown",
                    value_sats=value_sats,
                    confidence_score=conf_score,
                    confidence_level=self._get_confidence_level(conf_score),
                    path_length=len(current_path),
                    coinjoins_passed=current_cj_count,
                    trail_status=TrailStatus.DEAD_END,
                    reasoning=reasoning,
                    path=current_path
                ))
                result.total_traced_sats += value_sats
            else:
                # Spent - try to find where it went
                if electrs and address:
                    spending_txid = await self._find_spending_tx(current_txid, current_vout, address)
                    
                    if spending_txid:
                        spending_tx = await self._get_transaction(spending_txid)
                        if spending_tx:
                            # Add all outputs of spending tx to queue
                            for out_idx, out in enumerate(spending_tx.get("vout", [])):
                                out_value = int(out.get("value", 0) * 100_000_000)
                                if (spending_txid, out_idx) not in visited:
                                    queue.append((
                                        spending_txid,
                                        out_idx,
                                        depth + 1,
                                        current_cj_count,
                                        current_path,
                                        out_value
                                    ))
                    else:
                        # Spent but can't find spending tx
                        conf_score, reasoning = self._calculate_path_confidence(current_path, start_value)
                        reasoning.append("UTXO spent but spending transaction not found")
                        
                        destinations.append(ProbableDestination(
                            address=address or "unknown",
                            value_sats=value_sats,
                            confidence_score=conf_score * 0.3,
                            confidence_level=ConfidenceLevel.LOW,
                            path_length=len(current_path),
                            coinjoins_passed=current_cj_count,
                            trail_status=TrailStatus.LOST,
                            reasoning=reasoning,
                            path=current_path
                        ))
                else:
                    # No Electrs - can't follow
                    conf_score, reasoning = self._calculate_path_confidence(current_path, start_value)
                    reasoning.append("Cannot follow spent output (Electrs required)")
                    
                    destinations.append(ProbableDestination(
                        address=address or "unknown",
                        value_sats=value_sats,
                        confidence_score=conf_score * 0.5,
                        confidence_level=self._get_confidence_level(conf_score * 0.5),
                        path_length=len(current_path),
                        coinjoins_passed=current_cj_count,
                        trail_status=TrailStatus.LOST,
                        reasoning=reasoning,
                        path=current_path
                    ))
        
        # Sort destinations by confidence
        destinations.sort(key=lambda d: d.confidence_score, reverse=True)
        result.probable_destinations = destinations
        result.coinjoins_encountered = len(coinjoin_txids)
        
        # Calculate overall privacy score
        result.overall_privacy_score = self._calculate_overall_privacy(result)
        result.privacy_rating = self._get_privacy_rating(result.overall_privacy_score)
        
        # Generate summary and recommendations
        result.summary = self._generate_summary(result)
        result.recommendations = self._generate_recommendations(result)
        
        result.execution_time_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
        
        return result
    
    def _calculate_overall_privacy(self, result: KYCTraceResult) -> float:
        """Calculate overall privacy score (0-100, higher = more private)."""
        if not result.probable_destinations:
            return 100.0  # Nothing traceable = maximum privacy
        
        # Factors that improve privacy:
        score = 0.0
        
        # Factor 1: Proportion untraceable (0-40 points)
        total = result.original_value_sats
        if total > 0:
            untraceable_ratio = result.total_untraceable_sats / total
            score += untraceable_ratio * 40
        
        # Factor 2: CoinJoins used (0-30 points)
        if result.coinjoins_encountered >= 2:
            score += 30
        elif result.coinjoins_encountered == 1:
            score += 15
        
        # Factor 3: No high-confidence destinations (0-20 points)
        high_conf = [d for d in result.probable_destinations if d.confidence_level == ConfidenceLevel.HIGH]
        if not high_conf:
            score += 20
        elif len(high_conf) == 1:
            score += 5
        
        # Factor 4: Path complexity (0-10 points)
        avg_path_length = sum(d.path_length for d in result.probable_destinations) / max(len(result.probable_destinations), 1)
        score += min(avg_path_length * 2, 10)
        
        return min(score, 100.0)
    
    def _get_privacy_rating(self, score: float) -> str:
        """Convert privacy score to rating."""
        if score >= 80:
            return "excellent"
        elif score >= 60:
            return "good"
        elif score >= 40:
            return "moderate"
        elif score >= 20:
            return "poor"
        else:
            return "very_poor"
    
    def _generate_summary(self, result: KYCTraceResult) -> str:
        """Generate human-readable summary."""
        high_conf = [d for d in result.probable_destinations if d.confidence_level == ConfidenceLevel.HIGH]
        med_conf = [d for d in result.probable_destinations if d.confidence_level == ConfidenceLevel.MEDIUM]
        
        if result.overall_privacy_score >= 80:
            return f"Excellent privacy! Your funds are well protected. {result.coinjoins_encountered} CoinJoin(s) detected in paths."
        elif result.overall_privacy_score >= 60:
            return f"Good privacy. Most trails are cold or have low confidence. Found {len(high_conf)} high-confidence destination(s)."
        elif result.overall_privacy_score >= 40:
            return f"Moderate privacy. An adversary could potentially trace some funds. Found {len(high_conf)} high-confidence and {len(med_conf)} medium-confidence destination(s)."
        elif result.overall_privacy_score >= 20:
            return f"Poor privacy. Your funds can be traced with reasonable confidence to {len(high_conf)} address(es)."
        else:
            return f"Very poor privacy. Your funds are easily traceable to {len(high_conf)} address(es) with high confidence."
    
    def _generate_recommendations(self, result: KYCTraceResult) -> List[str]:
        """Generate privacy improvement recommendations."""
        recs = []
        
        if result.coinjoins_encountered == 0:
            recs.append("Consider using CoinJoin (Whirlpool, Wasabi, or JoinMarket) to break the transaction trail")
        
        high_conf = [d for d in result.probable_destinations if d.confidence_level == ConfidenceLevel.HIGH]
        if high_conf:
            recs.append(f"You have {len(high_conf)} easily traceable destination(s). Consider moving these funds through a CoinJoin")
        
        if result.overall_privacy_score < 60:
            recs.append("Avoid consolidating UTXOs from different sources without mixing first")
            recs.append("Use a new address for each transaction to prevent address clustering")
        
        if not result.electrs_enabled:
            recs.append("Enable Electrs for more accurate forward tracing analysis")
        
        # Check for address reuse in paths
        all_addresses = []
        for dest in result.probable_destinations:
            for node in dest.path:
                if node.address:
                    all_addresses.append(node.address)
        
        if len(all_addresses) != len(set(all_addresses)):
            recs.append("Address reuse detected in your transaction history - this hurts privacy")
        
        if not recs:
            recs.append("Your privacy practices look good! Continue using CoinJoin and avoiding address reuse")
        
        return recs
    
    @classmethod
    def get_depth_presets(cls) -> Dict:
        """Get available depth presets for UI."""
        return cls.DEPTH_PRESETS


# Singleton
_kyc_tracer_instance: Optional[KYCPrivacyTracer] = None


def get_kyc_tracer() -> KYCPrivacyTracer:
    """Get or create KYC tracer instance."""
    global _kyc_tracer_instance
    if _kyc_tracer_instance is None:
        _kyc_tracer_instance = KYCPrivacyTracer()
    return _kyc_tracer_instance
