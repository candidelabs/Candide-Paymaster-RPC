from rest_framework import serializers
from .models import Operation
from gnosis.eth.django.serializers import EthereumAddressField, HexadecimalField
from hexbytes import HexBytes


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
    nonce = serializers.IntegerField()
    initCode = HexadecimalField2(allow_blank=True)
    callData = HexadecimalField2()
    callGas = serializers.IntegerField()
    verificationGas = serializers.IntegerField()
    preVerificationGas = serializers.IntegerField()
    maxFeePerGas = serializers.IntegerField()
    maxPriorityFeePerGas = serializers.IntegerField()
    paymaster = EthereumAddressField(allow_zero_address=True)
    paymasterData = HexadecimalField2(allow_blank=True)
    signature = HexadecimalField2(max_length=65, min_length=65,allow_blank=True)

    def create(self, validated_data):
        return Operation.objects.create(**validated_data)
