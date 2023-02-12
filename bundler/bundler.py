from web3.exceptions import TimeExhausted

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
def calcPreVerificationGas(request):
    opLength = len(packUserOp(request))
    return opLength * 5 + 18000
  
@method
def eth_getOperationsGasValues(request) -> Result:
    serialzer = OperationSerialzer(data=request, many=True)

    if serialzer.is_valid(raise_exception=True):
        operations = serialzer.save()
    else:
        return Error(400, "BAD REQUEST")

    gasFees = getGasFees()

    operationsDict = serialzer.data
    results = []
    for op in operationsDict:
        operation = dict(op)
        callGas = 250000  # TODO : should be dynamic
        verificationGas = 10**5  # TODO : should be dynamic
        preVerificationGas = calcPreVerificationGas(operation)
        maxFeePerGas = w3.toWei(gasFees["medium"]["suggestedMaxFeePerGas"], 'gwei')
        maxPriorityFeePerGas = w3.toWei(gasFees["medium"]["suggestedMaxPriorityFeePerGas"], 'gwei')
        results.append(
            {
                "callGas": callGas,
                "verificationGas": verificationGas,
                "preVerificationGas": preVerificationGas,
                "maxFeePerGas": maxFeePerGas,
                "maxPriorityFeePerGas": maxPriorityFeePerGas,
            }
        )

    return Success(results)

#a module manager contract needs to be deployed before deploying the Gnosis safe
#proxy include in initCode
def deployModuleManager(salt) -> bool:
    #todo: add verification for salt to be bytes32
    
    f = open("bundler/moduleManagerInitCode", "r")
    moduleManagerInitCode = f.read()
    f.close()

    w3 = Web3(Web3.HTTPProvider(env('HTTPProvider')))

    abi = '[{"inputs":[{"internalType":"bytes","name":"_initCode","type":"bytes"},{"internalType":"bytes32","name":"_salt","type":"bytes32"}],"name":"deploy","outputs":[{"internalType":"address payable","name":"createdContract","type":"address"}],"stateMutability":"nonpayable","type":"function"}]'
    singletonFactory = w3.eth.contract(address=env('SingletonFactory_add'), abi=abi)
    transactionTemplate = singletonFactory.functions.deploy(
        moduleManagerInitCode,
        salt
        ) 

    gasFees = getGasFees()

    txnDict = {
            "chainId": env('chainId'),
            "from": env('bundler_pub'),
            "nonce": w3.eth.get_transaction_count(env('bundler_pub')),
            'gas': 4800000
    }
    
    if(env('isGanache') == "True"): #as ganache evm doesn't support maxFeePerGas & maxPriorityFeePerGas
        txnDict.update({
            'gasPrice': math.ceil(float(gasFees["medium"]["suggestedMaxFeePerGas"]))
        })
    else:
        txnDict.update({
            'maxFeePerGas': w3.toWei(gasFees["medium"]["suggestedMaxFeePerGas"], 'gwei'),
            'maxPriorityFeePerGas': w3.toWei(gasFees["medium"]["suggestedMaxPriorityFeePerGas"], 'gwei'),
        })

    transaction = transactionTemplate.build_transaction(txnDict)

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
    print('\033[96m' + "Bundle Operation received." + '\033[39m')

    for operation in request:
        moduleManagerSalt = operation['moduleManagerSalt']
        if moduleManagerSalt != "" and moduleManagerSalt != "0x":
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

    opsGas = 0
    for op in bundleDict:
        opsGas += op["callGas"] + op["verificationGas"] + op["preVerificationGas"]

    transactionTemplate = entryPoint.functions.handleOps([dict(op) for op in bundleDict], 
        address)

    try:
        gasEstimation = transactionTemplate.estimate_gas()
        gasEstimation = max(opsGas, gasEstimation * 1.4)
    except Exception as inst:
        print('\033[91m' + "Bundle operation failed (Gas estimation reverted): " + str(inst) + '\033[39m')
        return Error(2, "failed-to-submit", data={"status": "failed-to-submit", "txHash": None})

    gasFees = getGasFees()

    txnDict = {
            "chainId": env('chainId'),
            "from": env('bundler_pub'),
            "nonce": w3.eth.get_transaction_count(env('bundler_pub')),
            'gas': math.ceil(gasEstimation),
    }

    if env('isGanache') == "True": #as ganache evm doesn't support maxFeePerGas & maxPriorityFeePerGas
        txnDict.update({
            'gasPrice': math.ceil(float(gasFees["medium"]["suggestedMaxFeePerGas"]))
        })
    else:
        txnDict.update({
            'maxFeePerGas': w3.toWei(gasFees["medium"]["suggestedMaxFeePerGas"], 'gwei'),
            'maxPriorityFeePerGas': w3.toWei(gasFees["medium"]["suggestedMaxPriorityFeePerGas"], 'gwei'),
        })
       
    transaction = transactionTemplate.build_transaction(txnDict)

    sign_store_txn = w3.eth.account.sign_transaction(
        transaction, private_key=env('bundler_pk')
    )
    tx_hash = ""
    try:
        send_tx = w3.eth.send_raw_transaction(sign_store_txn.rawTransaction)
        tx_hash = str(send_tx.hex())
        tx_receipt = w3.eth.wait_for_transaction_receipt(send_tx, timeout=3)
        print('\033[92m' + "Bundle Sent (" + tx_hash + ") - with state: " + str(tx_receipt['status']) + '\033[39m')
        bundle.status = 'Successful'
        bundle.save()

        for operation in operations:
            operation.bundle = bundle
            operation.save()
       
        return Success({"status": "success", "txHash": tx_hash})
    except TimeExhausted as inst:
        print('\033[92m' + "Bundle operation timeout: " + str(inst) + '\033[39m')

        bundle.status = 'Pending'
        bundle.save()

        for operation in operations:
            operation.bundle = bundle
            operation.save()

        return Success({"status": "pending", "txHash": tx_hash})
    except Exception as inst:
        print('\033[91m' + "Bundle operation failed: " + str(inst) + '\033[39m')
        bundle.status = 'Failure'
        bundle.save()
       
        for operation in operations:
            operation.bundle = bundle
            operation.save()

        return Error(2, "failed", data={"status": "failed", "txHash": tx_hash})

@method
def eth_getRequestIds(request) -> Result:

    serialzer = OperationSerialzer(data=request, many=True)
    
    if serialzer.is_valid():
        serialzer.save()
    else:
        return Error(400, "BAD REQUEST")

    w3 = Web3(Web3.HTTPProvider(env('HTTPProvider')))
   
    abi = [{"inputs":[{"components":[{"internalType":"address","name":"sender","type":"address"},{"internalType":"uint256","name":"nonce","type":"uint256"},{"internalType":"bytes","name":"initCode","type":"bytes"},{"internalType":"bytes","name":"callData","type":"bytes"},{"internalType":"uint256","name":"callGas","type":"uint256"},{"internalType":"uint256","name":"verificationGas","type":"uint256"},{"internalType":"uint256","name":"preVerificationGas","type":"uint256"},{"internalType":"uint256","name":"maxFeePerGas","type":"uint256"},{"internalType":"uint256","name":"maxPriorityFeePerGas","type":"uint256"},{"internalType":"address","name":"paymaster","type":"address"},{"internalType":"bytes","name":"paymasterData","type":"bytes"},{"internalType":"bytes","name":"signature","type":"bytes"}],"internalType":"struct UserOperation","name":"userOp","type":"tuple"}],"name":"getRequestId","outputs":[{"internalType":"bytes32","name":"","type":"bytes32"}],"stateMutability":"view","type":"function"},{"inputs":[{"internalType":"bytes","name":"initCode","type":"bytes"},{"internalType":"uint256","name":"salt","type":"uint256"}],"name":"getSenderAddress","outputs":[{"internalType":"address","name":"","type":"address"}],"stateMutability":"view","type":"function"}]
    
    entryPoint = w3.eth.contract(address=env('entryPoint_add'), abi=abi)

    ops = serialzer.data
    result = []
    for operation in ops:
        opDict = dict(operation)
        requestId = entryPoint.functions.getRequestId(opDict).call()
        result.append(requestId.hex())

    return Success(result)


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