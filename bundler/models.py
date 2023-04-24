from django.db import models
from django.core.validators import MinValueValidator, int_list_validator
from django.core import exceptions
from django.utils.translation import gettext_lazy as _
from hexbytes import HexBytes
from .utils import validate_checksumed_address, fast_to_checksum_address
try:
    from django.db import DefaultConnectionProxy

    connection = DefaultConnectionProxy()
except ImportError:
    from django.db import connections

    connection = connections["default"]

NULL_ADDRESS: str = "0x" + "0" * 40


class HexField(models.CharField):
    """
    Field to store hex values (without 0x). Returns hex with 0x prefix.

    On Database side a CharField is used.
    """

    description = "Stores a hex value into a CharField. DEPRECATED, use a BinaryField"

    def from_db_value(self, value, expression, connection):
        return self.to_python(value)

    def to_python(self, value):
        return value if value is None else HexBytes(value).hex()

    def get_prep_value(self, value):
        if value is None:
            return value
        elif isinstance(value, HexBytes):
            return value.hex()[
                2:
            ]  # HexBytes.hex() retrieves hexadecimal with '0x', remove it
        elif isinstance(value, bytes):
            return value.hex()  # bytes.hex() retrieves hexadecimal without '0x'
        else:  # str
            return HexBytes(value).hex()[2:]

    def formfield(self, **kwargs):
        # We need max_lenght + 2 on forms because of `0x`
        defaults = {"max_length": self.max_length + 2}
        # TODO: Handle multiple backends with different feature flags.
        if self.null and not connection.features.interprets_empty_strings_as_nulls:
            defaults["empty_value"] = None
        defaults.update(kwargs)
        return super().formfield(**defaults)

    def clean(self, value, model_instance):
        value = self.to_python(value)
        self.validate(value, model_instance)
        # Validation didn't work because of `0x`
        self.run_validators(value[2:])
        return value


class Uint256Field(models.DecimalField):
    """
    Field to store ethereum uint256 values. Uses Decimal db type without decimals to store
    in the database, but retrieve as `int` instead of `Decimal` (https://docs.python.org/3/library/decimal.html)
    """

    description = _("Ethereum uint256 number")

    def __init__(self, *args, **kwargs):
        kwargs["max_digits"] = 79  # 2 ** 256 is 78 digits
        kwargs["decimal_places"] = 0
        super().__init__(*args, **kwargs)

    def deconstruct(self):
        name, path, args, kwargs = super().deconstruct()
        del kwargs["max_digits"]
        del kwargs["decimal_places"]
        return name, path, args, kwargs

    def from_db_value(self, value, expression, connection):
        if value is None:
            return value
        return int(value)


class EthereumAddressField(models.CharField):
    default_validators = [validate_checksumed_address]
    description = "DEPRECATED. Use `EthereumAddressV2Field`. Ethereum address (EIP55)"
    default_error_messages = {
        "invalid": _('"%(value)s" value must be an EIP55 checksummed address.'),
    }

    def __init__(self, *args, **kwargs):
        kwargs["max_length"] = 42
        super().__init__(*args, **kwargs)

    def deconstruct(self):
        name, path, args, kwargs = super().deconstruct()
        del kwargs["max_length"]
        return name, path, args, kwargs

    def from_db_value(self, value, expression, connection):
        return self.to_python(value)

    def to_python(self, value):
        value = super().to_python(value)
        if value:
            try:
                return fast_to_checksum_address(value)
            except ValueError:
                raise exceptions.ValidationError(
                    self.error_messages["invalid"],
                    code="invalid",
                    params={"value": value},
                )
        else:
            return value

    def get_prep_value(self, value):
        value = super().get_prep_value(value)
        return self.to_python(value)


class Operation(models.Model):
    sender = EthereumAddressField(default=NULL_ADDRESS)
    nonce = Uint256Field(default=0, validators=[MinValueValidator(0)])
    initCode = HexField(max_length=200000, null=True, blank=True)
    callData = HexField(max_length=200000)
    callGasLimit = Uint256Field(default=0, validators=[MinValueValidator(0)])
    verificationGasLimit = Uint256Field(default=0, validators=[MinValueValidator(0)])
    preVerificationGas = Uint256Field(default=0, validators=[MinValueValidator(0)])
    maxFeePerGas = Uint256Field(default=0, validators=[MinValueValidator(0)])
    maxPriorityFeePerGas = Uint256Field(default=0, validators=[MinValueValidator(0)])
    paymasterAndData = HexField(max_length=200000, null=True, blank=True)
    signature = HexField(max_length=65, null=True, blank=True)
    status = models.CharField(max_length=200, null=True, blank=True)
    bundle = models.ForeignKey("Bundle", on_delete=models.CASCADE, null=True, blank=True)


class Bundle(models.Model):
    beneficiary = EthereumAddressField(default=NULL_ADDRESS)
    status = models.CharField(max_length=200)


class ERC20ApprovedToken(models.Model):
    name = models.CharField(max_length=200, default="ERC20", unique=True)
    chains = models.JSONField()