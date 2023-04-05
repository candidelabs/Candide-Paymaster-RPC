from .models import Operation
from django.utils.translation import gettext_lazy as _

from hexbytes import HexBytes
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from .utils import fast_is_checksum_address


class EthereumAddressField(serializers.Field):
    """
    Ethereum address checksumed
    https://github.com/ethereum/EIPs/blob/master/EIPS/eip-55.md
    """

    def __init__(
            self,
            allow_zero_address: bool = False,
            allow_sentinel_address: bool = False,
            **kwargs
    ):
        self.allow_zero_address = allow_zero_address
        self.allow_sentinel_address = allow_sentinel_address
        super().__init__(**kwargs)

    def to_representation(self, obj):
        return obj

    def to_internal_value(self, data):
        # Check if address is valid
        try:
            if not fast_is_checksum_address(data):
                raise ValueError
            elif int(data, 16) == 0 and not self.allow_zero_address:
                raise ValidationError("0x0 address is not allowed")
            elif int(data, 16) == 1 and not self.allow_sentinel_address:
                raise ValidationError("0x1 address is not allowed")
        except ValueError:
            raise ValidationError("Address %s is not checksumed" % data)

        return data


class HexadecimalField(serializers.Field):
    """
    Serializes hexadecimal values starting by `0x`. Empty values should be None or just `0x`.
    """

    default_error_messages = {
        "invalid": _("{value} is not an hexadecimal value."),
        "blank": _("This field may not be blank."),
        "max_length": _(
            "Ensure this field has no more than {max_length} hexadecimal chars (not counting 0x)."
        ),
        "min_length": _(
            "Ensure this field has at least {min_length} hexadecimal chars (not counting 0x)."
        ),
    }

    def __init__(self, **kwargs):
        self.allow_blank = kwargs.pop("allow_blank", False)
        self.max_length = kwargs.pop("max_length", None)
        self.min_length = kwargs.pop("min_length", None)
        super().__init__(**kwargs)

    def to_representation(self, obj):
        if not obj:
            return "0x"

        # We can get another types like `memoryview` from django models. `to_internal_value` is not used
        # when you provide an object instead of a json using `data`. Make sure everything is HexBytes.
        if hasattr(obj, "hex"):
            obj = HexBytes(obj.hex())
        elif not isinstance(obj, HexBytes):
            obj = HexBytes(obj)
        return obj.hex()

    def to_internal_value(self, data):
        if isinstance(data, (bytes, memoryview)):
            data = data.hex()
        elif isinstance(data, str):
            data = data.strip()  # Trim spaces
            if data.startswith("0x"):  # Remove 0x prefix
                data = data[2:]
        elif data is None:
            pass
        else:
            self.fail("invalid", value=data)

        if not data:
            if self.allow_blank:
                return None
            else:
                self.fail("blank")

        try:
            data_hex = HexBytes(data)
            data_len = len(data_hex)
            if self.min_length and data_len < self.min_length:
                self.fail("min_length", min_length=data_len)
            elif self.max_length and data_len > self.max_length:
                self.fail("max_length", max_length=data_len)
            return data_hex
        except ValueError:
            self.fail("invalid", value=data)


class HexadecimalField2(HexadecimalField):
    """
    Modied to_internal_value function to return bytes(0) instead of None if allow_blank
    """

    def to_internal_value(self, data):
        if isinstance(data, (bytes, memoryview)):
            data = data.hex()
        elif isinstance(data, str):
            data = data.strip()  # Trim spaces
            if data.startswith("0x"):  # Remove 0x prefix
                data = data[2:]
        elif data is None:
            pass
        else:
            self.fail("invalid", value=data)

        if not data:
            if self.allow_blank:
                # return None
                return bytes(0)
            else:
                self.fail("blank")

        try:
            data_hex = HexBytes(data)
            data_len = len(data_hex)
            if self.min_length and data_len < self.min_length:
                self.fail("min_length", min_length=data_len)
            elif self.max_length and data_len > self.max_length:
                self.fail("max_length", max_length=data_len)
            return data_hex
        except ValueError:
            self.fail("invalid", value=data)


class OperationSerialzer(serializers.Serializer):
    # class Meta:
    #     list_serializer_class = BundleSerialzer
    sender = EthereumAddressField()
    nonce = HexadecimalField()
    initCode = HexadecimalField2(allow_blank=True)
    callData = HexadecimalField2(allow_blank=True)
    callGasLimit = HexadecimalField()
    verificationGasLimit = HexadecimalField()
    preVerificationGas = HexadecimalField()
    maxFeePerGas = HexadecimalField()
    maxPriorityFeePerGas = HexadecimalField()
    paymasterAndData = HexadecimalField2(allow_blank=True)
    signature = HexadecimalField2(max_length=65, min_length=65, allow_blank=True)

    def create(self, validated_data):
        return Operation.objects.create(**validated_data)