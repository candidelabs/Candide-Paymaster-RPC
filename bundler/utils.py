from typing import Union
from eth_typing import AnyAddress, ChecksumAddress, HexStr
from eth_utils import to_normalized_address
from sha3 import keccak_256
from django.core.exceptions import ValidationError


def validate_checksumed_address(address):
    if not fast_is_checksum_address(address):
        raise ValidationError(
            "%(address)s has an invalid checksum",
            params={"address": address},
        )


def fast_keccak_hex(value: bytes) -> HexStr:
    """
    Same as `fast_keccak`, but it's a little more optimal calling `hexdigest()`
    than calling `digest()` and then `hex()`
    :param value:
    :return: Keccak256 used by ethereum as an hex string (not 0x prefixed)
    """
    return HexStr(keccak_256(value).hexdigest())


def fast_is_checksum_address(value: Union[AnyAddress, str, bytes]) -> bool:
    """
    Fast version to check if an address is a checksum_address
    :param value:
    :return: `True` if checksummed, `False` otherwise
    """
    if not isinstance(value, str) or len(value) != 42 or not value.startswith("0x"):
        return False
    try:
        return fast_to_checksum_address(value) == value
    except ValueError:
        return False


def fast_to_checksum_address(value: Union[AnyAddress, str, bytes]) -> ChecksumAddress:
    """
    Converts to checksum_address. Uses more optimal `pysha3` instead of `eth_utils` for keccak256 calculation
    :param value:
    :return:
    """
    norm_address = to_normalized_address(value)[2:]
    address_hash = fast_keccak_hex(norm_address.encode())
    return _build_checksum_address(norm_address, address_hash)


def _build_checksum_address(
    norm_address: HexStr, address_hash: HexStr
) -> ChecksumAddress:
    """
    https://github.com/ethereum/EIPs/blob/master/EIPS/eip-55.md
    :param norm_address: address in lowercase (not 0x prefixed)
    :param address_hash: keccak256 of `norm_address` (not 0x prefixed)
    :return:
    """
    return ChecksumAddress(
        "0x"
        + (
            "".join(
                (
                    norm_address[i].upper()
                    if int(address_hash[i], 16) > 7
                    else norm_address[i]
                )
                for i in range(0, 40)
            )
        )
    )