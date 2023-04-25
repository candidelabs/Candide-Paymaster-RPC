import math

from .models import ERC20ApprovedToken
from .serializers import OperationSerialzer

from jsonrpcserver import method, Result, Success, dispatch, Error
from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponse

import environ
import requests
from web3 import Web3
from web3.middleware import geth_poa_middleware
from hexbytes import HexBytes
import re
from eth_account.messages import defunct_hash_message

env = environ.Env()


# Todo: check wallet balance if it has the required tokens to pay for the paymaster fees
# Todo: accept the full bundle as an input and check the approve operation
@method
def pm_sponsorUserOperation(request, token_address) -> Result:
    w3 = Web3(Web3.HTTPProvider(env('HTTPProvider')))
    chainId = str(env('chainId'))
    if chainId == "10":
        w3.middleware_onion.inject(geth_poa_middleware, layer=0)
    print('\033[96m' + "Paymaster Operation received." + '\033[39m')
    token_object = ERC20ApprovedToken.objects.filter(chains__has_key=chainId).filter(chains__icontains=token_address)
    if len(token_object) < 1:
        return Error(2, "Unsupported token", data="")

    token = token_object.first().chains[chainId]
    if not token["enabled"]:
        return Error(2, "Unsupported token", data="")

    serialzer = OperationSerialzer(data=request)

    if not serialzer.is_valid():
        return Error(400, "BAD REQUEST")

    op = dict(serialzer.data)
    op["maxFeePerGas"] = int(op["maxFeePerGas"], 16)
    op["maxPriorityFeePerGas"] = int(op["maxPriorityFeePerGas"], 16)
    op["callGasLimit"] = int(op["callGasLimit"], 16)
    op["verificationGasLimit"] = int(op["verificationGasLimit"], 16)
    op["preVerificationGas"] = int(op["preVerificationGas"], 16)
    op["nonce"] = int(op["nonce"], 16)

    abi = [{"inputs":[{"components":[{"internalType":"address","name":"sender","type":"address"},{"internalType":"uint256","name":"nonce","type":"uint256"},{"internalType":"bytes","name":"initCode","type":"bytes"},{"internalType":"bytes","name":"callData","type":"bytes"},{"internalType":"uint256","name":"callGasLimit","type":"uint256"},{"internalType":"uint256","name":"verificationGasLimit","type":"uint256"},{"internalType":"uint256","name":"preVerificationGas","type":"uint256"},{"internalType":"uint256","name":"maxFeePerGas","type":"uint256"},{"internalType":"uint256","name":"maxPriorityFeePerGas","type":"uint256"},{"internalType":"bytes","name":"paymasterAndData","type":"bytes"},{"internalType":"bytes","name":"signature","type":"bytes"}],"internalType":"struct UserOperation","name":"userOp","type":"tuple"},{"components":[{"internalType":"contract IERC20Metadata","name":"token","type":"address"},{"internalType":"enum CandidePaymaster.SponsoringMode","name":"mode","type":"uint8"},{"internalType":"uint48","name":"validUntil","type":"uint48"},{"internalType":"uint256","name":"fee","type":"uint256"},{"internalType":"uint256","name":"exchangeRate","type":"uint256"},{"internalType":"bytes","name":"signature","type":"bytes"}],"internalType":"struct CandidePaymaster.PaymasterData","name":"paymasterData","type":"tuple"}],"name":"getHash","outputs":[{"internalType":"bytes32","name":"","type":"bytes32"}],"stateMutability":"view","type":"function"}]
    paymaster = w3.eth.contract(address=env('paymaster_add'), abi=abi)

    exchange_rate = _get_token_rate(token)

    paymasterData = [
        token["address"],
        1,  # SponsoringMode (GAS ONLY)
        w3.eth.get_block("latest").timestamp + 180,  # validUntil 3 minutes in the future
        0,  # Fee (in case mode == 0)
        exchange_rate,  # Exchange Rate
        b'',
    ]

    hash = paymaster.functions.getHash(op, paymasterData).call()
    hash = defunct_hash_message(hash)
    bundlerSigner = w3.eth.account.from_key(env('bundler_pk'))
    sig = bundlerSigner.signHash(hash)
    paymasterData[-1] = HexBytes(sig.signature.hex())

    paymasterAndData = (
          str(paymasterData[0][2:])
        + str("{0:0{1}x}".format(paymasterData[1], 2))
        + str("{0:0{1}x}".format(paymasterData[2], 12))
        + str("{0:0{1}x}".format(paymasterData[3], 64))
        + str("{0:0{1}x}".format(paymasterData[4], 64))
        + sig.signature.hex()[2:]
    )

    return Success(paymasterAndData)

@method
def pm_getApprovedTokens() -> Result:
    result = []
    approved_tokens = ERC20ApprovedToken.objects.filter(chains__has_key=env('chainId'))
    for approvedToken in approved_tokens:
        token = approvedToken.chains[env('chainId')]
        exchange_rate = _get_token_rate(token)
        result.append({
            "address": token["address"],
            "paymaster": env('paymaster_add'),
            "exchangeRate": exchange_rate
        })
    return Success(result)


def _get_token_rate(token):
    rate_request = requests.get(token["exchangeRateSource"])
    rate_float = 1 / float(re.search(r'"eth":(\d+\.\d+)', rate_request.content.decode()).group(1))
    rate = math.ceil(rate_float * (10 ** token["decimals"]))
    return rate


@csrf_exempt
def jsonrpc(request):
    return HttpResponse(
        dispatch(request.body.decode()), content_type="application/json"
    )