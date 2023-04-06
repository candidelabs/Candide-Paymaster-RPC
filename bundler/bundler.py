from functools import reduce

from web3.exceptions import TimeExhausted

from .serializers import OperationSerialzer

from jsonrpcserver import method, Result, Success, dispatch, Error
from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponse

from web3 import Web3
import environ

from eth_abi import encode

import math
import requests
env = environ.Env()


@method
def eth_getGasFees() -> Result:
    return Success(getGasFees())


def getGasFees():
    if env('chainId') == '420' or env('chainId') == '10':
        gasFees = {"medium": {"suggestedMaxFeePerGas": 0.001, "suggestedMaxPriorityFeePerGas": 0.001}}
        return gasFees
    if env('chainId') == '11155111':
        gasFees = {"medium": {"suggestedMaxFeePerGas": 1.51, "suggestedMaxPriorityFeePerGas": 1.5}}
        return gasFees
    api_url = "https://gas-api.metaswap.codefi.network/networks/" + env('chainId') + "/suggestedGasFees"
    gasFees = requests.get(api_url)
    return gasFees.json()


def calc_preverification_gas(user_operation) -> int:
    userOp = user_operation

    fixed = 21000
    per_user_operation = 18300
    per_user_operation_word = 4
    zero_byte = 4
    non_zero_byte = 16
    bundle_size = 1
    sigSize = 65

    # userOp.preVerificationGas = fixed
    # userOp.signature = bytes(sigSize)
    packed = pack_user_operation(userOp)

    cost_list = list(map(lambda x: zero_byte if x == 0 else non_zero_byte, packed))
    call_data_cost = reduce(lambda x, y: x + y, cost_list)

    lengthInWord = (len(packed) + 31) / 32
    pre_verification_gas = (
        call_data_cost
        + (fixed / bundle_size)
        + per_user_operation
        + per_user_operation_word * lengthInWord
    )

    return math.ceil(pre_verification_gas)


def pack_user_operation(user_operation):
    return encode(
        [
            "address",
            "uint256",
            "bytes",
            "bytes",
            "uint256",
            "uint256",
            "uint256",
            "uint256",
            "uint256",
            "bytes",
            "bytes",
        ],
        [
            user_operation["sender"],
            int(str(user_operation["nonce"]), 16),
            bytes(user_operation["initCode"], 'ascii'),
            bytes(user_operation["callData"], 'ascii'),
            int(str(user_operation["callGasLimit"]), 16),
            int(str(user_operation["verificationGasLimit"]), 16),
            int(str(user_operation["preVerificationGas"]), 16),
            int(str(user_operation["maxFeePerGas"]), 16),
            int(str(user_operation["maxPriorityFeePerGas"]), 16),
            bytes(user_operation["paymasterAndData"], 'ascii'),
            bytes(user_operation["signature"], 'ascii')
        ],
    )[66:-64]


@method
def eth_estimateUserOperationGas(request) -> Result:
    serializer = OperationSerialzer(data=request)

    if not serializer.is_valid():
        return Error(400, "BAD REQUEST")

    w3 = Web3(Web3.HTTPProvider(env('HTTPProvider')))

    op = dict(serializer.data)
    rawTx = {
        "from": env('entryPoint_add'),
        "to": op["sender"],
        "data": op["callData"],
    }

    try:
        callGasLimit = w3.eth.estimate_gas(rawTx)
    except Exception as inst:
        return Error(2, "execution-reverted", data={"reason": "execution-reverted"})

    verificationGasLimit = 95000
    op["callGasLimit"] = callGasLimit
    op["verificationGasLimit"] = verificationGasLimit
    preVerificationGas = calc_preverification_gas(op)

    return Success({
        "callGasLimit": hex(callGasLimit),
        "verificationGasLimit": hex(verificationGasLimit),
        "preVerificationGas": hex(preVerificationGas),
    })


@method
def eth_sendUserOperation(request) -> Result:
    print('\033[96m' + "Bundle Operation received." + '\033[39m')

    serialzer = OperationSerialzer(data=request)

    if not serialzer.is_valid():
        return Error(400, "BAD REQUEST")

    w3 = Web3(Web3.HTTPProvider(env('HTTPProvider')))

    abi = [{"inputs": [{"components": [{"internalType": "address", "name": "sender", "type": "address"},{"internalType": "uint256", "name": "nonce", "type": "uint256"},{"internalType": "bytes", "name": "initCode", "type": "bytes"},{"internalType": "bytes", "name": "callData", "type": "bytes"},{"internalType": "uint256", "name": "callGasLimit", "type": "uint256"},{"internalType": "uint256", "name": "verificationGasLimit", "type": "uint256"},{"internalType": "uint256", "name": "preVerificationGas", "type": "uint256"},{"internalType": "uint256", "name": "maxFeePerGas", "type": "uint256"},{"internalType": "uint256", "name": "maxPriorityFeePerGas", "type": "uint256"},{"internalType": "bytes", "name": "paymasterAndData", "type": "bytes"},{"internalType": "bytes", "name": "signature", "type": "bytes"}],"internalType": "struct UserOperation[]", "name": "ops", "type": "tuple[]"},{"internalType": "address payable", "name": "beneficiary", "type": "address"}],"name": "handleOps", "outputs": [], "stateMutability": "nonpayable", "type": "function"}]

    entryPoint = w3.eth.contract(address=env('entryPoint_add'), abi=abi)
    address = w3.to_checksum_address(env('bundler_pub'))

    op = dict(serialzer.data)
    op["maxFeePerGas"] = int(op["maxFeePerGas"], 16)
    op["maxPriorityFeePerGas"] = int(op["maxPriorityFeePerGas"], 16)
    op["callGasLimit"] = int(op["callGasLimit"], 16)
    op["verificationGasLimit"] = int(op["verificationGasLimit"], 16)
    op["preVerificationGas"] = int(op["preVerificationGas"], 16)
    op["nonce"] = int(op["nonce"], 16)
    opGas = op["callGasLimit"] + op["verificationGasLimit"]

    transactionTemplate = entryPoint.functions.handleOps([op], address)

    try:
        gasEstimation = transactionTemplate.estimate_gas()
        gasEstimation = max(opGas, gasEstimation * 1.4)
    except Exception as inst:
        print('\033[91m' + "Bundle operation failed (Gas estimation reverted): " + str(inst) + '\033[39m')
        gasEstimation = 5000000
        # return Error(2, "failed-to-submit", data={"status": "failed-to-submit", "txHash": None})

    gasFees = getGasFees()

    txnDict = {
        "chainId": int(env('chainId')),
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
            'maxFeePerGas': w3.to_wei(gasFees["medium"]["suggestedMaxFeePerGas"], 'gwei'),
            'maxPriorityFeePerGas': w3.to_wei(gasFees["medium"]["suggestedMaxPriorityFeePerGas"], 'gwei'),
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
        return Success({"status": "success", "txHash": tx_hash})
    except TimeExhausted as inst:
        print('\033[92m' + "Bundle operation timeout: " + str(inst) + '\033[39m')
        return Success({"status": "pending", "txHash": tx_hash})
    except Exception as inst:
        print('\033[91m' + "Bundle operation failed: " + str(inst) + '\033[39m')
        return Error(2, "failed", data={"status": "failed", "txHash": tx_hash})


@method
def eth_supportedEntryPoints() -> Result:
    return Success(env('entryPoint_add'))


@method
def eth_chainId() -> Result:
    return Success(env('chainId'))


@csrf_exempt
def jsonrpc(request):
    return HttpResponse(
        dispatch(request.body.decode()), content_type="application/json"
    )