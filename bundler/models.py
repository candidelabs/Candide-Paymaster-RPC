from django.db import models
from django.core.validators import MinValueValidator

from gnosis.eth.django.models import EthereumAddressField, Uint256Field, HexField
from gnosis.eth.constants import NULL_ADDRESS

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
    status  = models.CharField(max_length=200, null=True, blank=True)
    bundle = models.ForeignKey("Bundle", on_delete=models.CASCADE, null=True, blank=True)

class Bundle(models.Model):
    beneficiary = EthereumAddressField(default=NULL_ADDRESS)
    status  = models.CharField(max_length=200)

class ERC20ApprovedToken(models.Model):
    name = models.CharField(max_length=200, default="ERC20", unique=True)
    address = EthereumAddressField(default=NULL_ADDRESS, unique=True)
    isActive  = models.BooleanField(default=False)
    tokenToEthPrice = Uint256Field(default=0, validators=[MinValueValidator(0)])