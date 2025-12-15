"""
ChainForensics - Electrs/Fulcrum Client
Full Electrum protocol implementation for address lookups.
"""
import asyncio
import hashlib
import json
import logging
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass

from app.config import settings

logger = logging.getLogger("chainforensics.electrs")


class ElectrsError(Exception):
    """Electrs client error."""
    def __init__(self, code: int, message: str):
        self.code = code
        self.message = message
        super().__init__(f"Electrs Error {code}: {message}")


@dataclass
class AddressBalance:
    """Address balance information."""
    address: str
    confirmed_sats: int
    unconfirmed_sats: int
    
    @property
    def confirmed_btc(self) -> float:
        return self.confirmed_sats / 100_000_000
    
    @property
    def unconfirmed_btc(self) -> float:
        return self.unconfirmed_sats / 100_000_000
    
    @property
    def total_sats(self) -> int:
        return self.confirmed_sats + self.unconfirmed_sats
    
    @property
    def total_btc(self) -> float:
        return self.total_sats / 100_000_000
    
    def to_dict(self) -> Dict:
        return {
            "address": self.address,
            "confirmed_sats": self.confirmed_sats,
            "confirmed_btc": self.confirmed_btc,
            "unconfirmed_sats": self.unconfirmed_sats,
            "unconfirmed_btc": self.unconfirmed_btc,
            "total_sats": self.total_sats,
            "total_btc": self.total_btc
        }


@dataclass
class AddressUTXO:
    """UTXO belonging to an address."""
    txid: str
    vout: int
    value_sats: int
    height: int  # 0 if unconfirmed
    
    @property
    def value_btc(self) -> float:
        return self.value_sats / 100_000_000
    
    @property
    def is_confirmed(self) -> bool:
        return self.height > 0
    
    def to_dict(self) -> Dict:
        return {
            "txid": self.txid,
            "vout": self.vout,
            "value_sats": self.value_sats,
            "value_btc": self.value_btc,
            "height": self.height,
            "is_confirmed": self.is_confirmed
        }


@dataclass
class AddressTransaction:
    """Transaction involving an address."""
    txid: str
    height: int  # 0 if unconfirmed
    fee: Optional[int] = None
    
    @property
    def is_confirmed(self) -> bool:
        return self.height > 0
    
    def to_dict(self) -> Dict:
        return {
            "txid": self.txid,
            "height": self.height,
            "is_confirmed": self.is_confirmed,
            "fee": self.fee
        }


class ElectrsClient:
    """
    Full Electrum protocol client for Electrs/Fulcrum.
    
    Implements the Electrum protocol over TCP for address-based queries.
    Reference: https://electrumx.readthedocs.io/en/latest/protocol-methods.html
    """
    
    def __init__(self, host: str = None, port: int = None):
        self.host = host or settings.ELECTRS_HOST
        self.port = port or settings.ELECTRS_PORT
        self._reader: Optional[asyncio.StreamReader] = None
        self._writer: Optional[asyncio.StreamWriter] = None
        self._request_id = 0
        self._lock = asyncio.Lock()
        self._connected = False
    
    @property
    def is_configured(self) -> bool:
        """Check if Electrs is configured."""
        return bool(self.host and self.port)
    
    async def connect(self) -> bool:
        """Connect to Electrs server."""
        if not self.is_configured:
            logger.warning("Electrs not configured (ELECTRS_HOST not set)")
            return False
        
        if self._connected and self._writer and not self._writer.is_closing():
            return True
        
        try:
            self._reader, self._writer = await asyncio.wait_for(
                asyncio.open_connection(self.host, self.port),
                timeout=10.0
            )
            self._connected = True
            logger.info(f"Connected to Electrs at {self.host}:{self.port}")
            return True
        except asyncio.TimeoutError:
            logger.error(f"Timeout connecting to Electrs at {self.host}:{self.port}")
            self._connected = False
            return False
        except Exception as e:
            logger.error(f"Failed to connect to Electrs: {e}")
            self._connected = False
            return False
    
    async def disconnect(self):
        """Disconnect from Electrs server."""
        if self._writer:
            try:
                self._writer.close()
                await self._writer.wait_closed()
            except Exception:
                pass
        self._reader = None
        self._writer = None
        self._connected = False
    
    async def _call(self, method: str, params: List = None) -> Any:
        """Make JSON-RPC call to Electrs."""
        if params is None:
            params = []
        
        async with self._lock:
            # Ensure connected
            if not await self.connect():
                raise ElectrsError(-1, "Not connected to Electrs")
            
            self._request_id += 1
            request = {
                "jsonrpc": "2.0",
                "id": self._request_id,
                "method": method,
                "params": params
            }
            
            try:
                # Send request
                request_line = json.dumps(request) + "\n"
                self._writer.write(request_line.encode())
                await self._writer.drain()
                
                # Read response
                response_line = await asyncio.wait_for(
                    self._reader.readline(),
                    timeout=30.0
                )
                
                if not response_line:
                    raise ElectrsError(-1, "Empty response from Electrs")
                
                response = json.loads(response_line.decode())
                
                if "error" in response and response["error"]:
                    error = response["error"]
                    raise ElectrsError(
                        error.get("code", -1),
                        error.get("message", "Unknown error")
                    )
                
                return response.get("result")
                
            except asyncio.TimeoutError:
                await self.disconnect()
                raise ElectrsError(-1, "Request timed out")
            except json.JSONDecodeError as e:
                raise ElectrsError(-1, f"Invalid JSON response: {e}")
            except Exception as e:
                if isinstance(e, ElectrsError):
                    raise
                await self.disconnect()
                raise ElectrsError(-1, f"Request failed: {e}")
    
    # ============== Address Conversion ==============
    
    @staticmethod
    def address_to_scripthash(address: str) -> str:
        """
        Convert a Bitcoin address to an Electrum scripthash.
        
        The scripthash is the SHA256 hash of the scriptPubKey, reversed.
        This is what Electrum protocol uses for address lookups.
        """
        import hashlib
        
        # Decode address to get scriptPubKey
        script_pubkey = ElectrsClient._address_to_script_pubkey(address)
        
        # SHA256 hash
        sha256_hash = hashlib.sha256(script_pubkey).digest()
        
        # Reverse bytes (Electrum uses little-endian)
        reversed_hash = sha256_hash[::-1]
        
        return reversed_hash.hex()
    
    @staticmethod
    def _address_to_script_pubkey(address: str) -> bytes:
        """Convert Bitcoin address to scriptPubKey bytes."""
        
        # P2PKH (Legacy) - starts with 1
        if address.startswith('1'):
            pubkey_hash = ElectrsClient._base58_decode_check(address)[1:]  # Remove version byte
            # OP_DUP OP_HASH160 <20 bytes> OP_EQUALVERIFY OP_CHECKSIG
            return bytes([0x76, 0xa9, 0x14]) + pubkey_hash + bytes([0x88, 0xac])
        
        # P2SH (Script Hash) - starts with 3
        elif address.startswith('3'):
            script_hash = ElectrsClient._base58_decode_check(address)[1:]  # Remove version byte
            # OP_HASH160 <20 bytes> OP_EQUAL
            return bytes([0xa9, 0x14]) + script_hash + bytes([0x87])
        
        # P2WPKH (Native SegWit) - starts with bc1q, 42 chars
        elif address.startswith('bc1q') and len(address) == 42:
            _, data = ElectrsClient._bech32_decode(address)
            witness_program = ElectrsClient._convert_bits(data[1:], 5, 8, False)
            # OP_0 <20 bytes>
            return bytes([0x00, 0x14]) + bytes(witness_program)
        
        # P2WSH (Native SegWit Script) - starts with bc1q, 62 chars
        elif address.startswith('bc1q') and len(address) == 62:
            _, data = ElectrsClient._bech32_decode(address)
            witness_program = ElectrsClient._convert_bits(data[1:], 5, 8, False)
            # OP_0 <32 bytes>
            return bytes([0x00, 0x20]) + bytes(witness_program)
        
        # P2TR (Taproot) - starts with bc1p
        elif address.startswith('bc1p'):
            _, data = ElectrsClient._bech32m_decode(address)
            witness_program = ElectrsClient._convert_bits(data[1:], 5, 8, False)
            # OP_1 <32 bytes>
            return bytes([0x51, 0x20]) + bytes(witness_program)
        
        # Testnet addresses
        elif address.startswith(('m', 'n')):
            pubkey_hash = ElectrsClient._base58_decode_check(address)[1:]
            return bytes([0x76, 0xa9, 0x14]) + pubkey_hash + bytes([0x88, 0xac])
        
        elif address.startswith('2'):
            script_hash = ElectrsClient._base58_decode_check(address)[1:]
            return bytes([0xa9, 0x14]) + script_hash + bytes([0x87])
        
        elif address.startswith('tb1q'):
            _, data = ElectrsClient._bech32_decode(address)
            witness_program = ElectrsClient._convert_bits(data[1:], 5, 8, False)
            if len(witness_program) == 20:
                return bytes([0x00, 0x14]) + bytes(witness_program)
            else:
                return bytes([0x00, 0x20]) + bytes(witness_program)
        
        elif address.startswith('tb1p'):
            _, data = ElectrsClient._bech32m_decode(address)
            witness_program = ElectrsClient._convert_bits(data[1:], 5, 8, False)
            return bytes([0x51, 0x20]) + bytes(witness_program)
        
        else:
            raise ValueError(f"Unsupported address format: {address}")
    
    @staticmethod
    def _base58_decode_check(address: str) -> bytes:
        """Decode Base58Check encoded address."""
        alphabet = '123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz'
        
        # Decode base58
        num = 0
        for char in address:
            num = num * 58 + alphabet.index(char)
        
        # Convert to bytes
        combined = num.to_bytes(25, 'big')
        
        # Verify checksum
        checksum = combined[-4:]
        payload = combined[:-4]
        
        hash1 = hashlib.sha256(payload).digest()
        hash2 = hashlib.sha256(hash1).digest()
        
        if hash2[:4] != checksum:
            raise ValueError("Invalid checksum")
        
        return payload
    
    @staticmethod
    def _bech32_decode(address: str) -> Tuple[str, List[int]]:
        """Decode Bech32 address."""
        CHARSET = "qpzry9x8gf2tvdw0s3jn54khce6mua7l"
        
        # Find separator
        pos = address.rfind('1')
        if pos < 1 or pos + 7 > len(address):
            raise ValueError("Invalid bech32 address")
        
        hrp = address[:pos].lower()
        data_part = address[pos + 1:].lower()
        
        # Decode data
        data = []
        for c in data_part:
            if c not in CHARSET:
                raise ValueError(f"Invalid character: {c}")
            data.append(CHARSET.index(c))
        
        # Verify checksum (simplified - just return data without checksum)
        return hrp, data[:-6]
    
    @staticmethod
    def _bech32m_decode(address: str) -> Tuple[str, List[int]]:
        """Decode Bech32m address (for Taproot)."""
        # Same structure as bech32, different checksum constant
        return ElectrsClient._bech32_decode(address)
    
    @staticmethod
    def _convert_bits(data: List[int], from_bits: int, to_bits: int, pad: bool = True) -> List[int]:
        """Convert between bit sizes."""
        acc = 0
        bits = 0
        result = []
        maxv = (1 << to_bits) - 1
        
        for value in data:
            acc = (acc << from_bits) | value
            bits += from_bits
            while bits >= to_bits:
                bits -= to_bits
                result.append((acc >> bits) & maxv)
        
        if pad and bits:
            result.append((acc << (to_bits - bits)) & maxv)
        
        return result
    
    # ============== Server Methods ==============
    
    async def server_version(self) -> Dict:
        """Get server version information."""
        result = await self._call("server.version", ["ChainForensics", "1.4"])
        return {
            "server_software": result[0] if isinstance(result, list) else result,
            "protocol_version": result[1] if isinstance(result, list) and len(result) > 1 else "1.4"
        }
    
    async def server_banner(self) -> str:
        """Get server banner message."""
        return await self._call("server.banner")
    
    async def server_ping(self) -> bool:
        """Ping the server."""
        try:
            await self._call("server.ping")
            return True
        except Exception:
            return False
    
    # ============== Blockchain Methods ==============
    
    async def get_block_header(self, height: int) -> str:
        """Get block header at height (hex)."""
        return await self._call("blockchain.block.header", [height])
    
    async def get_block_headers(self, start_height: int, count: int) -> Dict:
        """Get multiple block headers."""
        return await self._call("blockchain.block.headers", [start_height, count])
    
    async def estimate_fee(self, blocks: int = 6) -> float:
        """Estimate fee rate (BTC/kB) for confirmation in n blocks."""
        return await self._call("blockchain.estimatefee", [blocks])
    
    async def get_tip(self) -> Dict:
        """Get current blockchain tip."""
        result = await self._call("blockchain.headers.subscribe")
        # Result can be a dict or sometimes just the header info
        if isinstance(result, dict):
            return {
                "height": result.get("height"),
                "hex": result.get("hex")
            }
        elif isinstance(result, list) and len(result) > 0:
            # Some servers return [{"height": ..., "hex": ...}]
            first = result[0] if isinstance(result[0], dict) else {}
            return {
                "height": first.get("height"),
                "hex": first.get("hex")
            }
        else:
            return {"height": None, "hex": None}
    
    # ============== Address/ScriptHash Methods ==============
    
    async def get_balance(self, address: str) -> AddressBalance:
        """Get balance for an address."""
        scripthash = self.address_to_scripthash(address)
        result = await self._call("blockchain.scripthash.get_balance", [scripthash])
        
        return AddressBalance(
            address=address,
            confirmed_sats=result.get("confirmed", 0),
            unconfirmed_sats=result.get("unconfirmed", 0)
        )
    
    async def get_history(self, address: str) -> List[AddressTransaction]:
        """Get transaction history for an address."""
        scripthash = self.address_to_scripthash(address)
        result = await self._call("blockchain.scripthash.get_history", [scripthash])
        
        transactions = []
        for item in result:
            transactions.append(AddressTransaction(
                txid=item.get("tx_hash"),
                height=item.get("height", 0),
                fee=item.get("fee")
            ))
        
        return transactions
    
    async def get_mempool(self, address: str) -> List[AddressTransaction]:
        """Get unconfirmed transactions for an address."""
        scripthash = self.address_to_scripthash(address)
        result = await self._call("blockchain.scripthash.get_mempool", [scripthash])
        
        transactions = []
        for item in result:
            transactions.append(AddressTransaction(
                txid=item.get("tx_hash"),
                height=0,
                fee=item.get("fee")
            ))
        
        return transactions
    
    async def get_utxos(self, address: str) -> List[AddressUTXO]:
        """Get unspent outputs for an address."""
        scripthash = self.address_to_scripthash(address)
        result = await self._call("blockchain.scripthash.listunspent", [scripthash])
        
        utxos = []
        for item in result:
            utxos.append(AddressUTXO(
                txid=item.get("tx_hash"),
                vout=item.get("tx_pos"),
                value_sats=item.get("value"),
                height=item.get("height", 0)
            ))
        
        return utxos
    
    # ============== Transaction Methods ==============
    
    async def get_transaction(self, txid: str, verbose: bool = True) -> Dict:
        """Get raw transaction."""
        return await self._call("blockchain.transaction.get", [txid, verbose])
    
    async def broadcast_transaction(self, raw_tx_hex: str) -> str:
        """Broadcast a raw transaction. Returns txid."""
        return await self._call("blockchain.transaction.broadcast", [raw_tx_hex])
    
    async def get_merkle_proof(self, txid: str, height: int) -> Dict:
        """Get merkle proof for a transaction."""
        return await self._call("blockchain.transaction.get_merkle", [txid, height])
    
    async def get_tx_from_position(self, height: int, tx_pos: int, merkle: bool = False) -> str:
        """Get transaction hash from block position."""
        return await self._call("blockchain.transaction.id_from_pos", [height, tx_pos, merkle])
    
    # ============== High-Level Methods ==============
    
    async def get_address_info(self, address: str) -> Dict:
        """Get comprehensive address information."""
        balance = await self.get_balance(address)
        history = await self.get_history(address)
        utxos = await self.get_utxos(address)
        
        # Calculate stats
        total_received = 0
        total_sent = 0
        
        return {
            "address": address,
            "balance": balance.to_dict(),
            "transaction_count": len(history),
            "utxo_count": len(utxos),
            "first_seen_height": min((h.height for h in history if h.height > 0), default=None),
            "last_seen_height": max((h.height for h in history if h.height > 0), default=None),
            "transactions": [tx.to_dict() for tx in history[-50:]],  # Last 50 transactions
            "utxos": [utxo.to_dict() for utxo in utxos]
        }
    
    async def find_spending_tx(self, txid: str, vout: int) -> Optional[str]:
        """
        Find the transaction that spent a specific output.
        
        This is the key feature that Bitcoin Core RPC cannot do without txindex!
        """
        # First, get the transaction to find the output address
        tx = await self.get_transaction(txid, verbose=True)
        
        if not tx or "vout" not in tx:
            return None
        
        if vout >= len(tx["vout"]):
            return None
        
        output = tx["vout"][vout]
        script_pubkey = output.get("scriptPubKey", {})
        address = script_pubkey.get("address")
        
        if not address:
            # Try to extract from asm for non-standard scripts
            return None
        
        # Get all transactions for this address
        history = await self.get_history(address)
        
        # Look for a transaction that spends this output
        # This requires checking each transaction's inputs
        for hist_tx in history:
            if hist_tx.txid == txid:
                continue  # Skip the original transaction
            
            try:
                full_tx = await self.get_transaction(hist_tx.txid, verbose=True)
                if not full_tx:
                    continue
                
                for vin in full_tx.get("vin", []):
                    if vin.get("txid") == txid and vin.get("vout") == vout:
                        return hist_tx.txid
            except Exception:
                continue
        
        return None  # Output is unspent or spending tx not found
    
    async def check_dust_attack(self, address: str, dust_threshold_sats: int = 1000) -> Dict:
        """
        Check an address for potential dust attack UTXOs.
        
        Dust attacks send tiny amounts to track spending patterns.
        """
        utxos = await self.get_utxos(address)
        history = await self.get_history(address)
        
        dust_utxos = []
        suspicious_utxos = []
        
        for utxo in utxos:
            if utxo.value_sats <= dust_threshold_sats:
                dust_utxos.append(utxo.to_dict())
                
                # Check if this could be a dust attack
                # (received from unknown source, tiny amount)
                if utxo.value_sats <= 546:  # Bitcoin dust limit
                    suspicious_utxos.append({
                        **utxo.to_dict(),
                        "warning": "Below dust limit - likely dust attack",
                        "recommendation": "Do NOT spend with other UTXOs"
                    })
                elif utxo.value_sats <= dust_threshold_sats:
                    suspicious_utxos.append({
                        **utxo.to_dict(),
                        "warning": "Small UTXO - potential dust attack",
                        "recommendation": "Verify source before spending"
                    })
        
        return {
            "address": address,
            "dust_threshold_sats": dust_threshold_sats,
            "total_utxos": len(utxos),
            "dust_utxos_count": len(dust_utxos),
            "suspicious_count": len(suspicious_utxos),
            "dust_utxos": dust_utxos,
            "suspicious_utxos": suspicious_utxos,
            "total_dust_value_sats": sum(u["value_sats"] for u in dust_utxos),
            "recommendation": (
                "DANGER: Dust UTXOs detected! Do not consolidate these with your main UTXOs." 
                if suspicious_utxos else 
                "No suspicious dust UTXOs detected."
            )
        }


# Singleton instance
_electrs_instance: Optional[ElectrsClient] = None


def get_electrs() -> ElectrsClient:
    """Get or create Electrs client instance."""
    global _electrs_instance
    if _electrs_instance is None:
        _electrs_instance = ElectrsClient()
    return _electrs_instance


async def check_electrs_connection() -> Dict:
    """Check if Electrs is available and return status."""
    client = get_electrs()
    
    if not client.is_configured:
        return {
            "status": "not_configured",
            "message": "ELECTRS_HOST not set in environment"
        }
    
    try:
        if await client.connect():
            version = await client.server_version()
            tip = await client.get_tip()
            return {
                "status": "connected",
                "host": client.host,
                "port": client.port,
                "server": version.get("server_software") if isinstance(version, dict) else str(version),
                "protocol": version.get("protocol_version") if isinstance(version, dict) else "1.4",
                "tip_height": tip.get("height") if isinstance(tip, dict) else None
            }
    except Exception as e:
        logger.error(f"Electrs connection check failed: {e}")
        return {
            "status": "error",
            "host": client.host,
            "port": client.port,
            "error": str(e)
        }
    
    return {
        "status": "disconnected",
        "host": client.host,
        "port": client.port
    }