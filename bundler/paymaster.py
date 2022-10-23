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

#Todo: check wallet balance if it has the required tokens to pay for the paymaster fees
#Todo: accept the full bundle as an input and check the approve operation
@method
def eth_paymaster(request, 
    token = "0x03F1B4380995Fbf41652F75a38c9F74aD8aD73F5") -> Result:
    print('\033[96m' + "Paymaster Operation received." + '\033[4m')

    token_object = ERC20ApprovedToken.objects.filter(address = token)

    if(len(token_object) < 1 or not token_object.first().isActive):
        print("No token")
        return Error(2, "Unsupported token", data="")

    serialzer = OperationSerialzer(data=request)
    
    if serialzer.is_valid():
        serialzer.save()
    else:
        return Error(400, "BAD REQUEST")

    op = serialzer.data

    #TODO : fetch live token price
    maxTokenCost = 5
    maxTokenCostHex = str("{0:0{1}x}".format(maxTokenCost,40))
    
    #TODO : compute dynamically
    costOfPost = 10**18
    costOfPostHex = str("{0:0{1}x}".format(costOfPost,40))

    abiEncoded = eth_abi.encode_abi(
        ['address', 'uint256', 
        'bytes32', 
        'bytes32',
        'uint256', 'uint256', 'uint256', 'uint256', 
        'uint256', 'address',
        'uint160','uint160','address'],
        [op['sender'], op['nonce'],
        w3.solidityKeccak(['bytes'], [op['initCode']]),
        w3.solidityKeccak(['bytes'], [op['callData']]),
        op['callGas'],op['verificationGas'],op['preVerificationGas'],op['maxFeePerGas'],
        op['maxPriorityFeePerGas'], op['paymaster'],
        maxTokenCost, costOfPost, token])
    hash = w3.solidityKeccak(['bytes'], ['0x' + abiEncoded.hex()])

    bundlerSigner = w3.eth.account.from_key(env('bundler_pk'))
    sig = bundlerSigner.signHash(hash)

    paymasterData = maxTokenCostHex + costOfPostHex + token[2:] + sig.signature.hex()[2:]

    print('\033[92m' + "Paymaster data : " + paymasterData + '\033[4m')
    return Success(paymasterData)

@method
def eth_paymaster_approved_tokens() -> Result:
    arrovedTokens = [token['address'] for token in ERC20ApprovedToken.objects.values('address')]
    return Success([str({"address":arrovedToken, "price":1}) for arrovedToken in arrovedTokens])

@csrf_exempt
def jsonrpc(request):
    return HttpResponse(
        dispatch(request.body.decode()), content_type="application/json"
    )