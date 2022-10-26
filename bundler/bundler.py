from .models import  Bundle
from .serializers import OperationSerialzer

from jsonrpcserver import method, Result, Success, dispatch, Error
from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponse

from web3 import Web3
import environ

from web3.auto import w3
import eth_abi

import math
import requests

from hexbytes import HexBytes
env = environ.Env()

@method
def eth_getGasFees() -> Result:
    return Success(getGasFees())

def getGasFees():
    api_url = "https://gas-api.metaswap.codefi.network/networks/" + env('chainId') + "/suggestedGasFees"
    gasFees = requests.get(api_url)
    return gasFees.json()

#only to calculate preVerificationGas
def packUserOp(operation):
    abiEncoded = eth_abi.encode_abi(
        [
            'address', 'uint256', 'bytes', 'bytes',
            'uint256', 'uint256', 'uint256', 'uint256', 
            'uint256', 'address', 'bytes', 'bytes'
        ],
        [
            operation["sender"],
            operation["nonce"],
            bytes(operation["initCode"], 'ascii'),
            bytes(operation["callData"], 'ascii'),
            operation["callGas"],
            operation["verificationGas"],
            operation["preVerificationGas"],
            operation["maxFeePerGas"],
            operation["maxPriorityFeePerGas"],
            operation["paymaster"],
            bytes(operation["paymasterData"], 'ascii'),
            bytes(operation["signature"], 'ascii')
        ])
    return abiEncoded.hex()

#calculate preVerificationGas
@method
def calcPreVerificationGas(request) -> Result:
    opLength = len(packUserOp(request))
    return Success(opLength * 5 + 18000)
  
@method
def eth_getOperationGasValues(request) -> Result:
    serialzer = OperationSerialzer(data=request)
    op = serialzer.data
    gasFees = getGasFees()
    op["callGas"] = 215000              #TODO : should be dynamic
    op["verificationGas"] = 645000      #TODO : should be dynamic
    op["preVerificationGas"] = calcPreVerificationGas(request)
    op["maxFeePerGas"] = gasFees["medium"]["suggestedMaxFeePerGas"]
    op["maxPriorityFeePerGas"] = gasFees["medium"]["maxPriorityFeePerGas"]

    return Success(op)

#a module manager contract needs to be deployed before deploying the Gnosis safe
#proxy include in initCode
def deployModuleManager(salt: int) -> bool:
    f = open("bundler/moduleManagerInitCode", "r")
    moduleManagerInitCode = f.read()
    f.close()
    
    abi = '[{"inputs":[{"internalType":"bytes","name":"_initCode","type":"bytes"},{"internalType":"bytes32","name":"_salt","type":"bytes32"}],"name":"deploy","outputs":[{"internalType":"address payable","name":"createdContract","type":"address"}],"stateMutability":"nonpayable","type":"function"}]'
    singletonFactory = w3.eth.contract(address=env('SingletonFactory_add'), abi=abi)
    transactionTemplate = singletonFactory.functions.deploy(
        moduleManagerInitCode,
        "0x{:064x}".format(salt)
        ) 

    gasEstimation = transactionTemplate.estimate_gas()

    gasFees = getGasFees()

    gasLimit = math.ceil(gasEstimation * 1.3)
        
    transaction = transactionTemplate.build_transaction(
        {
            "chainId": 5,
            "from": env('bundler_pub'),
            "nonce": w3.eth.get_transaction_count(env('bundler_pub')),
            'gas': gasLimit,
            'gasPrice': math.ceil(float(gasFees["medium"]["suggestedMaxFeePerGas"])),
        }
    )

    sign_store_txn = w3.eth.account.sign_transaction(
        transaction, private_key=env('bundler_pk')
    )
    
    try:
        send_tx = w3.eth.send_raw_transaction(sign_store_txn.rawTransaction)
        tx_receipt = w3.eth.wait_for_transaction_receipt(send_tx)
        tx_hash = tx_receipt['transactionHash'].hex()
        print("ModuleManager Deployed - with state : " + str(tx_receipt['status']))
        print("Transaction hash : " + str(tx_hash))
        return True
    except Exception as inst:
        print("ModuleManager Deployment failed : " + str(inst))
        return False

@method
def eth_sendUserOperation(request) -> Result:
    print('\033[96m' + "Bundle Operation received." + '\033[0m')

    for operation in request:
        moduleManagerSalt = operation['moduleManagerSalt']
        if isinstance(moduleManagerSalt, str):
            if moduleManagerSalt.startswith("0x"):
                if moduleManagerSalt == "0x":
                    moduleManagerSalt = 0
                else:
                    moduleManagerSalt = int(moduleManagerSalt, 16)
            else:
                if moduleManagerSalt == "":
                    moduleManagerSalt = 0
                else:
                    moduleManagerSalt = int(moduleManagerSalt)
        if(moduleManagerSalt != 0):
            deployModuleManager(moduleManagerSalt)
    
    bundle = Bundle(beneficiary=env('bundler_pub'))

    serialzer = OperationSerialzer(data=request, many=True)
    
    if serialzer.is_valid():
        operations = serialzer.save()
    else:
        return Error(400, "BAD REQUEST")

    w3 = Web3(Web3.HTTPProvider(env('HTTPProvider')))
   
    abi = [{"inputs":[{"components":[{"internalType":"address","name":"sender","type":"address"},{"internalType":"uint256","name":"nonce","type":"uint256"},{"internalType":"bytes","name":"initCode","type":"bytes"},{"internalType":"bytes","name":"callData","type":"bytes"},{"internalType":"uint256","name":"callGas","type":"uint256"},{"internalType":"uint256","name":"verificationGas","type":"uint256"},{"internalType":"uint256","name":"preVerificationGas","type":"uint256"},{"internalType":"uint256","name":"maxFeePerGas","type":"uint256"},{"internalType":"uint256","name":"maxPriorityFeePerGas","type":"uint256"},{"internalType":"address","name":"paymaster","type":"address"},{"internalType":"bytes","name":"paymasterData","type":"bytes"},{"internalType":"bytes","name":"signature","type":"bytes"}],"internalType":"struct UserOperation[]","name":"ops","type":"tuple[]"},{"internalType":"address payable","name":"beneficiary","type":"address"}],"name":"handleOps","outputs":[],"stateMutability":"nonpayable","type":"function"}]

    entryPoint = w3.eth.contract(address=env('entryPoint_add'), abi=abi)
    address = Web3.toChecksumAddress(env('bundler_pub'))

    bundleDict = serialzer.data

    transactionTemplate = entryPoint.functions.handleOps([dict(op) for op in bundleDict], 
        address)

    gasEstimation = transactionTemplate.estimate_gas()
    gasFees = getGasFees()

    transaction = transactionTemplate.build_transaction(
        {
            "chainId": 5,
            "from": env('bundler_pub'),
            "nonce": w3.eth.get_transaction_count(env('bundler_pub')),
            'gas': math.ceil(gasEstimation * 1.2),
            'gasPrice': math.ceil(float(gasFees["medium"]["suggestedMaxFeePerGas"])),
        }
    )


    sign_store_txn = w3.eth.account.sign_transaction(
        transaction, private_key=env('bundler_pk')
    )
    
    try:
        send_tx = w3.eth.send_raw_transaction(sign_store_txn.rawTransaction)
        tx_receipt = w3.eth.wait_for_transaction_receipt(send_tx)
        tx_hash = tx_receipt['transactionHash'].hex()
        print('\033[92m' + "Bundle Sent - with state : " + str(tx_receipt['status']) + '\033[0m')
        print('\033[92m' + "Transaction hash : " + str(tx_hash))
        bundle.status='Successful'
        bundle.save()

        for operation in operations:
            operation.bundle = bundle
            operation.save()
       
        return Success("Success : " + str(tx_receipt))

    except Exception as inst:
        print('\033[91m' + "Bundle operation failed : " + str(inst) + '\033[0m')
        bundle.status='Failure'
        bundle.save()
       
        for operation in operations:
            operation.bundle = bundle
            operation.save()

        return Error(2, "Bundle operation failed", data=str(inst))

@method
def eth_getRequestId(request) -> Result:

    serialzer = OperationSerialzer(data=request)
    
    if serialzer.is_valid():
        serialzer.save()
    else:
        return Error(400, "BAD REQUEST")

    w3 = Web3(Web3.HTTPProvider(env('HTTPProvider')))
   
    abi = [{"inputs":[{"components":[{"internalType":"address","name":"sender","type":"address"},{"internalType":"uint256","name":"nonce","type":"uint256"},{"internalType":"bytes","name":"initCode","type":"bytes"},{"internalType":"bytes","name":"callData","type":"bytes"},{"internalType":"uint256","name":"callGas","type":"uint256"},{"internalType":"uint256","name":"verificationGas","type":"uint256"},{"internalType":"uint256","name":"preVerificationGas","type":"uint256"},{"internalType":"uint256","name":"maxFeePerGas","type":"uint256"},{"internalType":"uint256","name":"maxPriorityFeePerGas","type":"uint256"},{"internalType":"address","name":"paymaster","type":"address"},{"internalType":"bytes","name":"paymasterData","type":"bytes"},{"internalType":"bytes","name":"signature","type":"bytes"}],"internalType":"struct UserOperation","name":"userOp","type":"tuple"}],"name":"getRequestId","outputs":[{"internalType":"bytes32","name":"","type":"bytes32"}],"stateMutability":"view","type":"function"},{"inputs":[{"internalType":"bytes","name":"initCode","type":"bytes"},{"internalType":"uint256","name":"salt","type":"uint256"}],"name":"getSenderAddress","outputs":[{"internalType":"address","name":"","type":"address"}],"stateMutability":"view","type":"function"}]
    
    entryPoint = w3.eth.contract(address=env('entryPoint_add'), abi=abi)
    opDict = serialzer.data
   
    requestId = entryPoint.functions.getRequestId(opDict).call()

    return Success(requestId.hex())


@method
def eth_supportedEntryPoints() -> Result:
    return Success(env('entryPoint_add'))

@method
def eth_chainId() -> Result:
    return Success(env('chainId'))

@method
def eth_gasFee() -> Result:
    return Success(env('chainId'))

@csrf_exempt
def jsonrpc(request):
    return HttpResponse(
        dispatch(request.body.decode()), content_type="application/json"
    )