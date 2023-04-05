from .models import ERC20ApprovedToken
from .serializers import OperationSerialzer

from jsonrpcserver import method, Result, Success, dispatch, Error
from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponse

import environ
from web3 import Web3
from hexbytes import HexBytes

env = environ.Env()


# Todo: check wallet balance if it has the required tokens to pay for the paymaster fees
# Todo: accept the full bundle as an input and check the approve operation
@method
def eth_paymaster(request, token) -> Result:
    w3 = Web3(Web3.HTTPProvider(env('HTTPProvider')))
    print('\033[96m' + "Paymaster Operation received." + '\033[39m')

    token_object = ERC20ApprovedToken.objects.filter(address=token).filter(chains__has_key=env('chainId'))
    if len(token_object) < 1:
        return Error(2, "Unsupported token", data="")

    token = token_object.first()

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

    abi = [{"inputs":[{"components":[{"internalType":"address","name":"sender","type":"address"},{"internalType":"uint256","name":"nonce","type":"uint256"},{"internalType":"bytes","name":"initCode","type":"bytes"},{"internalType":"bytes","name":"callData","type":"bytes"},{"internalType":"uint256","name":"callGasLimit","type":"uint256"},{"internalType":"uint256","name":"verificationGasLimit","type":"uint256"},{"internalType":"uint256","name":"preVerificationGas","type":"uint256"},{"internalType":"uint256","name":"maxFeePerGas","type":"uint256"},{"internalType":"uint256","name":"maxPriorityFeePerGas","type":"uint256"},{"internalType":"bytes","name":"paymasterAndData","type":"bytes"},{"internalType":"bytes","name":"signature","type":"bytes"}],"internalType":"struct UserOperation","name":"userOp","type":"tuple"},{"components":[{"internalType":"contract IERC20Metadata","name":"token","type":"address"},{"internalType":"enum CandidePaymaster.SponsoringMode","name":"mode","type":"uint8"},{"internalType":"uint48","name":"validUntil","type":"uint48"},{"internalType":"uint256","name":"fee","type":"uint256"},{"internalType":"bytes","name":"signature","type":"bytes"}],"internalType":"struct CandidePaymaster.PaymasterData","name":"paymasterData","type":"tuple"}],"name":"getHash","outputs":[{"internalType":"bytes32","name":"","type":"bytes32"}],"stateMutability":"view","type":"function"}]
    paymaster = w3.eth.contract(address=env('paymaster_add'), abi=abi)

    paymasterData = [
        token.address,
        1,  # SponsoringMode (GAS ONLY)
        w3.eth.get_block("latest").timestamp + 300,  # validUntil 5 minutes in the future
        0,  # Fee (in case mode == 0)
        b'',
    ]

    hash = paymaster.functions.getHash(op, paymasterData).call()
    bundlerSigner = w3.eth.account.from_key(env('bundler_pk'))
    sig = bundlerSigner.signHash(hash)
    paymasterData[-1] = HexBytes(sig.signature.hex())

    paymasterAndData = (
          str(paymasterData[0][2:])
        + str("{0:0{1}x}".format(paymasterData[1], 2))
        + str("{0:0{1}x}".format(paymasterData[2], 12))
        + str("{0:0{1}x}".format(paymasterData[3], 64))
        + sig.signature.hex()[2:]
    )

    return Success(paymasterAndData)

@method
def eth_paymaster_approved_tokens() -> Result:
    aprrovedTokens = ERC20ApprovedToken.objects.filter(chains__has_key=env('chainId'))
    return Success([
        str({
            "address": aprrovedToken.address,
            "paymaster": env('paymaster_add'),
        }) for aprrovedToken in aprrovedTokens]
    )

@csrf_exempt
def jsonrpc(request):
    return HttpResponse(
        dispatch(request.body.decode()), content_type="application/json"
    )