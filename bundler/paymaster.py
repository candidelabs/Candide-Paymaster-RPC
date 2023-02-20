from .models import ERC20ApprovedToken
from .serializers import OperationSerialzer

from jsonrpcserver import method, Result, Success, dispatch, Error
from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponse

import environ

from web3.auto import w3
import eth_abi

from hexbytes import HexBytes

env = environ.Env()


# Todo: check wallet balance if it has the required tokens to pay for the paymaster fees
# Todo: accept the full bundle as an input and check the approve operation
@method
def eth_paymaster(request, token) -> Result:
    print('\033[96m' + "Paymaster Operation received." + '\033[39m')

    token_object = ERC20ApprovedToken.objects.filter(address=token)

    if len(token_object) < 1 or not token_object.first().isActive:
        return Error(2, "Unsupported token", data="")

    token = token_object.first()

    serialzer = OperationSerialzer(data=request)

    if serialzer.is_valid():
        serialzer.save()
    else:
        return Error(400, "BAD REQUEST")

    op = dict(serialzer.data)

    bundlerSigner = w3.eth.account.from_key(env('bundler_pk'))
    maxFeePerGas = int(op['maxFeePerGas'])
    callGasLimit = int(op['callGasLimit'])
    verificationGasLimit = int(op['verificationGasLimit'])
    preVerificationGas = int(op['preVerificationGas'])

    operationMaxEthCostUsingPaymaster = (callGasLimit + verificationGasLimit * 3 + preVerificationGas) * maxFeePerGas

    tokenAddress = token.address
    tokenToEthPrice = token.tokenToEthPrice  # tokenToEthPrice conversionRate
    maxTokenCost = int(operationMaxEthCostUsingPaymaster * (tokenToEthPrice / 10 ** 18))
    maxTokenCostHex = str("{0:0{1}x}".format(maxTokenCost, 40))

    costOfPost = verificationGasLimit * maxFeePerGas
    costOfPostHex = str("{0:0{1}x}".format(costOfPost, 40))

    abiEncoded = eth_abi.encode_abi(
        ['address', 'uint256',
         'bytes32',
         'bytes32',
         'uint256', 'uint256', 'uint256', 'uint256',
         'uint256', 'uint160', 'uint160', 'address'],
        [op['sender'], op['nonce'],
         w3.solidityKeccak(['bytes'], [op['initCode']]),
         w3.solidityKeccak(['bytes'], [op['callData']]),
         op['callGasLimit'], op['verificationGasLimit'], op['preVerificationGas'], op['maxFeePerGas'],
         op['maxPriorityFeePerGas'], maxTokenCost, costOfPost, tokenAddress])
    hash = w3.solidityKeccak(['bytes'], ['0x' + abiEncoded.hex()])
    sig = bundlerSigner.signHash(hash)
    paymasterData = maxTokenCostHex + costOfPostHex + tokenAddress[2:] + sig.signature.hex()[2:]

    return Success(paymasterData)


@method
def eth_getApproveAmount(request, token) -> Result:
    token_object = ERC20ApprovedToken.objects.filter(address=token)

    if len(token_object) < 1 or not token_object.first().isActive:
        return Error(2, "Unsupported token", data="")

    token = token_object.first()

    total = 0
    for op in request:
        callGas = int(op['callGas'])
        verificationGas = int(op['verificationGas'])
        preVerificationGas = int(op['preVerificationGas'])
        maxFeePerGas = int(op['maxFeePerGas'])

        operationMaxEthCostUsingPaymaster = (callGas + verificationGas * 3 + preVerificationGas) * maxFeePerGas

        tokenToEthPrice = token.tokenToEthPrice  # tokenToEthPrice conversionRate
        maxTokenCost = int(operationMaxEthCostUsingPaymaster * (tokenToEthPrice / 10 ** 18))

        total = total + maxTokenCost

    #todo: fetch and substract the contract allowance to the paymaster for the final result
    return Success(total)

@method
def eth_paymaster_approved_tokens() -> Result:
    aprrovedTokens = ERC20ApprovedToken.objects.filter(isActive=True)
    return Success([
        str({
            "address": aprrovedToken.address,
            "tokenToEthPrice": str(aprrovedToken.tokenToEthPrice)
        }) for aprrovedToken in aprrovedTokens]
    )

@csrf_exempt
def jsonrpc(request):
    return HttpResponse(
        dispatch(request.body.decode()), content_type="application/json"
    )